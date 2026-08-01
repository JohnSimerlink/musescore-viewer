"""Apply structured ops to a ScoreDocument with undo/redo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import PlannedOp, SelectionContext
from ..score.mscx import ScoreDocument
from .history import MutationLog

KEY_NAME_TO_FIFTHS = {
    "c": 0,
    "g": 1,
    "d": 2,
    "a": 3,
    "e": 4,
    "b": 5,
    "f#": 6,
    "gb": -6,
    "db": -5,
    "ab": -4,
    "eb": -3,
    "bb": -2,
    "f": -1,
}


@dataclass
class ApplyResult:
    op: PlannedOp
    summary: dict[str, Any] = field(default_factory=dict)


def _staff_filter(selection: SelectionContext | None) -> set[str] | None:
    if selection is None or not selection.staves:
        return None
    return set(selection.staves)


def _voice_filter(selection: SelectionContext | None) -> set[int] | None:
    if selection is None or not selection.voices:
        return None
    out: set[int] = set()
    for v in selection.voices:
        try:
            out.add(int(v))
        except ValueError:
            continue
    return out or None


class ApplyEngine:
    def __init__(self, document: ScoreDocument):
        self.log = MutationLog(document)
        self.document = self.log.document()
        self.clipboard: list[Any] | None = None  # list of Measure element deep copies per staff
        self.selection: SelectionContext | None = None
        self.revision = 0
        self._pending_base: ScoreDocument | None = None

    def _sync_doc(self) -> None:
        self.document = self.log.document()

    def _begin_mutation(self) -> None:
        """Clone current head so a failed mutation can discard work."""
        self._pending_base = self.document.clone()
        self.document = self._pending_base

    def _commit_mutation(self, tool: str, args: dict[str, Any], detail: str | None) -> None:
        self.log.append(tool=tool, args=args, detail=detail, document=self.document)
        self._sync_doc()
        self._pending_base = None
        self.revision += 1

    def _abort_mutation(self) -> None:
        self._sync_doc()
        self._pending_base = None

    def _push_undo(self) -> None:
        """Backward-compatible: start a mutating edit (snapshot taken at commit)."""
        self._begin_mutation()

    def _applied(self, op: PlannedOp) -> ApplyResult:
        if op.status == "error":
            if self._pending_base is not None:
                self._abort_mutation()
            return ApplyResult(op, summary=self.snapshot_summary())
        if self._pending_base is not None:
            self._commit_mutation(op.tool, op.args, op.detail)
        return ApplyResult(op, summary=self.snapshot_summary())

    def snapshot_summary(self) -> dict[str, Any]:
        return self.document.summary()

    def can_undo(self) -> bool:
        return self.log.can_undo()

    def can_redo(self) -> bool:
        return self.log.can_redo()

    def undo(self) -> ApplyResult:
        if not self.log.can_undo():
            return ApplyResult(
                PlannedOp(tool="undo", status="error", detail="Nothing to undo."),
            )
        self.log.undo()
        self._sync_doc()
        self.revision += 1
        return ApplyResult(
            PlannedOp(
                tool="undo",
                status="applied",
                detail=f"Undid last edit (head={self.log.head_id}).",
            ),
            summary=self.snapshot_summary(),
        )

    def redo(self) -> ApplyResult:
        if not self.log.can_redo():
            return ApplyResult(
                PlannedOp(tool="redo", status="error", detail="Nothing to redo."),
            )
        self.log.redo()
        self._sync_doc()
        self.revision += 1
        return ApplyResult(
            PlannedOp(
                tool="redo",
                status="applied",
                detail=f"Redid last edit (head={self.log.head_id}).",
            ),
            summary=self.snapshot_summary(),
        )

    def hop_to(self, event_id: str) -> ApplyResult:
        try:
            self.log.hop_to(event_id)
        except KeyError as exc:
            return ApplyResult(
                PlannedOp(tool="hop_to", args={"id": event_id}, status="error", detail=str(exc))
            )
        self._sync_doc()
        self.revision += 1
        return ApplyResult(
            PlannedOp(
                tool="hop_to",
                args={"id": event_id},
                status="applied",
                detail=f"Hopped to {event_id}.",
            ),
            summary=self.snapshot_summary(),
        )

    def label_version(self, name: str) -> ApplyResult:
        try:
            ev = self.log.label_current(name)
        except ValueError as exc:
            return ApplyResult(
                PlannedOp(tool="label_version", args={"name": name}, status="error", detail=str(exc))
            )
        return ApplyResult(
            PlannedOp(
                tool="label_version",
                args={"name": name, "id": ev.id},
                status="applied",
                detail=f"Labeled {ev.id} as '{name}'.",
            ),
            summary=self.snapshot_summary(),
        )

    def apply(self, tool: str, args: dict[str, Any] | None = None) -> ApplyResult:
        args = dict(args or {})
        handlers = {
            "transpose_selection": self._transpose,
            "delete_selection": self._delete_selection,
            "duplicate_measures": self._duplicate,
            "set_note_duration": self._set_duration,
            "set_selection": self._set_selection,
            "clear_selection": self._clear_selection,
            "add_note": self._add_note,
            "delete_note": self._delete_note,
            "add_rest": self._add_rest,
            "copy_selection": self._copy,
            "cut_selection": self._cut,
            "paste_selection": self._paste,
            "insert_measures": self._insert_measures,
            "delete_measures": self._delete_measures,
            "set_time_signature": self._set_time_signature,
            "set_key_signature": self._set_key_signature,
            "set_tempo": self._set_tempo,
            "add_dynamic": self._add_dynamic,
            "set_lyrics": self._set_lyrics,
            "undo": lambda _a: self.undo(),
            "redo": lambda _a: self.redo(),
            "hop_to": lambda a: self.hop_to(str(a.get("id") or a.get("event_id") or "")),
            "label_version": lambda a: self.label_version(str(a.get("name") or "")),
            "play_selection": self._play_selection,
            "set_selection_voices": self._set_selection_voices,
        }
        handler = handlers.get(tool)
        if handler is None:
            return ApplyResult(
                PlannedOp(
                    tool=tool,
                    args=args,
                    status="error",
                    detail=f"Unknown tool '{tool}'.",
                )
            )
        return handler(args)

    def _require_selection(self, args: dict[str, Any]) -> SelectionContext | PlannedOp:
        sel = args.get("selection")
        if isinstance(sel, SelectionContext):
            selection = sel
        elif isinstance(sel, dict):
            selection = SelectionContext.model_validate(sel)
        else:
            selection = self.selection
        if selection is None or selection.measure_start is None:
            return PlannedOp(
                tool=args.get("_tool", "selection"),
                args=args,
                status="error",
                detail="No measure selection provided.",
            )
        if selection.measure_end is None:
            selection.measure_end = selection.measure_start
        return selection

    def _transpose(self, args: dict[str, Any]) -> ApplyResult:
        args = {**args, "_tool": "transpose_selection"}
        sel = self._require_selection(args)
        if isinstance(sel, PlannedOp):
            sel.tool = "transpose_selection"
            return ApplyResult(sel)
        semitones = int(args.get("semitones", 0))
        self._push_undo()
        n = self.document.transpose_selection(
            semitones,
            measure_start=sel.measure_start or 1,
            measure_end=sel.measure_end or sel.measure_start or 1,
            staff_ids=_staff_filter(sel),
            voices=_voice_filter(sel),
        )
        return self._applied(
            PlannedOp(
                tool="transpose_selection",
                args={"semitones": semitones, "selection": sel.model_dump(exclude_none=True)},
                status="applied",
                detail=(
                    f"Transposed measures {sel.measure_start}–{sel.measure_end} "
                    f"by {semitones:+d} semitone(s) ({n} notes)."
                ),
            )
        )

    def _delete_selection(self, args: dict[str, Any]) -> ApplyResult:
        args = {**args, "_tool": "delete_selection"}
        sel = self._require_selection(args)
        if isinstance(sel, PlannedOp):
            sel.tool = "delete_selection"
            return ApplyResult(sel)
        self._push_undo()
        n = self.document.delete_selection(
            measure_start=sel.measure_start or 1,
            measure_end=sel.measure_end or sel.measure_start or 1,
            staff_ids=_staff_filter(sel),
            voices=_voice_filter(sel),
        )
        return self._applied(
            PlannedOp(
                tool="delete_selection",
                args={"selection": sel.model_dump(exclude_none=True)},
                status="applied",
                detail=f"Deleted content in measures {sel.measure_start}–{sel.measure_end} ({n} chords → rests).",
            )
        )

    def _duplicate(self, args: dict[str, Any]) -> ApplyResult:
        start = int(args["measure_start"])
        end = int(args["measure_end"])
        insert_after = args.get("insert_after")
        insert_after = int(insert_after) if insert_after is not None else None
        if start < 1 or end < start:
            return ApplyResult(
                PlannedOp(
                    tool="duplicate_measures",
                    args=args,
                    status="error",
                    detail="Invalid measure range.",
                )
            )
        self._push_undo()
        try:
            n = self.document.duplicate_measures(start, end, insert_after)
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="duplicate_measures",
                    args=args,
                    status="error",
                    detail=str(exc),
                )
            )
        target = insert_after if insert_after is not None else end
        return self._applied(
            PlannedOp(
                tool="duplicate_measures",
                args={
                    "measure_start": start,
                    "measure_end": end,
                    "insert_after": target,
                },
                status="applied",
                detail=f"Cloned measures {start}–{end} after measure {target} ({n} measures).",
            )
        )

    def _set_duration(self, args: dict[str, Any]) -> ApplyResult:
        duration = str(args.get("duration", ""))
        args = {**args, "_tool": "set_note_duration"}
        sel = self._require_selection(args)
        # duration may apply with selection optional for caret — require selection for MVP
        if isinstance(sel, PlannedOp):
            sel.tool = "set_note_duration"
            return ApplyResult(sel)
        self._push_undo()
        try:
            n = self.document.set_note_duration(
                duration,
                measure_start=sel.measure_start,
                measure_end=sel.measure_end,
                staff_ids=_staff_filter(sel),
                voices=_voice_filter(sel),
            )
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="set_note_duration",
                    args={"duration": duration},
                    status="error",
                    detail=str(exc),
                )
            )
        return self._applied(
            PlannedOp(
                tool="set_note_duration",
                args={
                    "duration": duration,
                    "selection": sel.model_dump(exclude_none=True),
                },
                status="applied",
                detail=f"Set {n} chord duration(s) to {duration} in measures {sel.measure_start}–{sel.measure_end}.",
            )
        )

    def _set_selection(self, args: dict[str, Any]) -> ApplyResult:
        start = int(args["measure_start"])
        end = int(args["measure_end"])
        if start < 1 or end < start:
            return ApplyResult(
                PlannedOp(
                    tool="set_selection",
                    args=args,
                    status="error",
                    detail="Invalid measure range.",
                )
            )
        voices = args.get("voices") or []
        staves = args.get("staves") or []
        self.selection = SelectionContext(
            measure_start=start,
            measure_end=end,
            voices=list(voices),
            staves=list(staves),
            label=f"Measures {start}–{end}",
        )
        return ApplyResult(
            PlannedOp(
                tool="set_selection",
                args={
                    "measure_start": start,
                    "measure_end": end,
                    "voices": voices,
                    "staves": staves,
                },
                status="applied",
                detail=f"Selection set to measures {start}–{end}.",
            ),
            summary=self.snapshot_summary(),
        )

    def _clear_selection(self, _args: dict[str, Any]) -> ApplyResult:
        self.selection = None
        return ApplyResult(
            PlannedOp(
                tool="clear_selection",
                args={},
                status="applied",
                detail="Selection cleared.",
            ),
            summary=self.snapshot_summary(),
        )

    def _set_selection_voices(self, args: dict[str, Any]) -> ApplyResult:
        if self.selection is None:
            return ApplyResult(
                PlannedOp(
                    tool="set_selection_voices",
                    args=args,
                    status="error",
                    detail="No selection to filter.",
                )
            )
        voices = list(args.get("voices") or [])
        staves = list(args.get("staves") or [])
        self.selection = self.selection.model_copy(
            update={"voices": voices, "staves": staves}
        )
        return ApplyResult(
            PlannedOp(
                tool="set_selection_voices",
                args={"voices": voices, "staves": staves},
                status="applied",
                detail=f"Selection filter voices={voices or 'all'} staves={staves or 'all'}.",
            ),
            summary=self.snapshot_summary(),
        )

    def _add_note(self, args: dict[str, Any]) -> ApplyResult:
        self._push_undo()
        try:
            self.document.add_note(
                pitch=int(args["pitch"]),
                duration=str(args.get("duration", "quarter")),
                measure=int(args["measure"]),
                beat=float(args.get("beat", 1.0)),
                staff_id=args.get("staff"),
                voice=int(args.get("voice", 1)),
            )
        except (KeyError, ValueError) as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(tool="add_note", args=args, status="error", detail=str(exc))
            )
        return self._applied(
            PlannedOp(
                tool="add_note",
                args=args,
                status="applied",
                detail=f"Added note pitch={args.get('pitch')} in measure {args.get('measure')}.",
            )
        )

    def _delete_note(self, args: dict[str, Any]) -> ApplyResult:
        self._push_undo()
        n = self.document.delete_note_at(
            measure=int(args.get("measure") or (self.selection.measure_start if self.selection else 1)),
            pitch=int(args["pitch"]) if args.get("pitch") is not None else None,
            staff_id=args.get("staff"),
        )
        if n == 0:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="delete_note",
                    args=args,
                    status="error",
                    detail="No matching note found.",
                )
            )
        return self._applied(
            PlannedOp(
                tool="delete_note",
                args=args,
                status="applied",
                detail=f"Deleted {n} note(s).",
            )
        )

    def _add_rest(self, args: dict[str, Any]) -> ApplyResult:
        self._push_undo()
        try:
            self.document.add_rest(
                duration=str(args.get("duration", "quarter")),
                measure=int(args["measure"]),
                beat=float(args.get("beat", 1.0)),
                staff_id=args.get("staff"),
                voice=int(args.get("voice", 1)),
            )
        except (KeyError, ValueError) as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(tool="add_rest", args=args, status="error", detail=str(exc))
            )
        return self._applied(
            PlannedOp(
                tool="add_rest",
                args=args,
                status="applied",
                detail=f"Added rest in measure {args.get('measure')}.",
            )
        )

    def _copy(self, args: dict[str, Any]) -> ApplyResult:
        args = {**args, "_tool": "copy_selection"}
        sel = self._require_selection(args)
        if isinstance(sel, PlannedOp):
            sel.tool = "copy_selection"
            return ApplyResult(sel)
        import copy as _copy

        clip = []
        for staff in self.document.staff_elements():
            measures = self.document.measures_for_staff(staff)
            chunk = [
                _copy.deepcopy(measures[i])
                for i in range((sel.measure_start or 1) - 1, sel.measure_end or 1)
            ]
            clip.append({"staff_id": staff.get("id"), "measures": chunk})
        self.clipboard = clip
        return ApplyResult(
            PlannedOp(
                tool="copy_selection",
                args={"selection": sel.model_dump(exclude_none=True)},
                status="applied",
                detail=f"Copied measures {sel.measure_start}–{sel.measure_end}.",
            ),
            summary=self.snapshot_summary(),
        )

    def _cut(self, args: dict[str, Any]) -> ApplyResult:
        copied = self._copy(args)
        if copied.op.status == "error":
            copied.op.tool = "cut_selection"
            return copied
        deleted = self._delete_selection(args)
        if deleted.op.status == "error":
            return deleted
        deleted.op.tool = "cut_selection"
        deleted.op.detail = f"Cut measures {self.selection.measure_start if self.selection else '?'}."
        # restore detail from copy range
        sel = args.get("selection") or (self.selection.model_dump() if self.selection else {})
        deleted.op.detail = f"Cut selection {sel}."
        deleted.op.args = {"selection": sel}
        return deleted

    def _paste(self, args: dict[str, Any]) -> ApplyResult:
        if not self.clipboard:
            return ApplyResult(
                PlannedOp(
                    tool="paste_selection",
                    args=args,
                    status="error",
                    detail="Clipboard empty.",
                )
            )
        target = int(args.get("target") or args.get("after_measure") or 0)
        if target < 0:
            return ApplyResult(
                PlannedOp(
                    tool="paste_selection",
                    args=args,
                    status="error",
                    detail="Invalid paste target.",
                )
            )
        import copy as _copy

        self._push_undo()
        for entry in self.clipboard:
            staff = next(
                (
                    s
                    for s in self.document.staff_elements()
                    if s.get("id") == entry.get("staff_id")
                ),
                None,
            )
            if staff is None:
                continue
            measure_nodes = [
                (i, el)
                for i, el in enumerate(list(staff))
                if el.tag.endswith("Measure") or el.tag == "Measure"
            ]
            if target == 0:
                abs_idx = measure_nodes[0][0] - 1 if measure_nodes else len(list(staff)) - 1
            else:
                if target > len(measure_nodes):
                    self._abort_mutation()
                    return ApplyResult(
                        PlannedOp(
                            tool="paste_selection",
                            args=args,
                            status="error",
                            detail="Paste target out of bounds.",
                        )
                    )
                abs_idx = measure_nodes[target - 1][0]
            for offset, m in enumerate(entry["measures"]):
                staff.insert(abs_idx + 1 + offset, _copy.deepcopy(m))
        return self._applied(
            PlannedOp(
                tool="paste_selection",
                args={"target": target},
                status="applied",
                detail=f"Pasted clipboard after measure {target}.",
            )
        )

    def _insert_measures(self, args: dict[str, Any]) -> ApplyResult:
        count = int(args.get("count", 1))
        after = int(args.get("after_measure", 0))
        self._push_undo()
        try:
            n = self.document.insert_measures(count, after)
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="insert_measures",
                    args=args,
                    status="error",
                    detail=str(exc),
                )
            )
        return self._applied(
            PlannedOp(
                tool="insert_measures",
                args={"count": count, "after_measure": after},
                status="applied",
                detail=f"Inserted {n} measure(s) after measure {after}.",
            )
        )

    def _delete_measures(self, args: dict[str, Any]) -> ApplyResult:
        start = int(args["measure_start"])
        end = int(args["measure_end"])
        self._push_undo()
        try:
            n = self.document.delete_measures(start, end)
        except (KeyError, ValueError) as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="delete_measures",
                    args=args,
                    status="error",
                    detail=str(exc),
                )
            )
        return self._applied(
            PlannedOp(
                tool="delete_measures",
                args={"measure_start": start, "measure_end": end},
                status="applied",
                detail=f"Deleted {n} measure(s) ({start}–{end}).",
            )
        )

    def _set_time_signature(self, args: dict[str, Any]) -> ApplyResult:
        num = int(args["numerator"])
        den = int(args["denominator"])
        measure = int(args.get("measure") or 1)
        self._push_undo()
        try:
            self.document.set_time_signature(num, den, measure)
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="set_time_signature",
                    args=args,
                    status="error",
                    detail=str(exc),
                )
            )
        return self._applied(
            PlannedOp(
                tool="set_time_signature",
                args={"numerator": num, "denominator": den, "measure": measure},
                status="applied",
                detail=f"Set time signature {num}/{den} at measure {measure}.",
            )
        )

    def _set_key_signature(self, args: dict[str, Any]) -> ApplyResult:
        if "fifths" in args and args["fifths"] is not None:
            fifths = int(args["fifths"])
        else:
            name = str(args.get("name") or "c").strip().lower().replace(" ", "")
            if name not in KEY_NAME_TO_FIFTHS:
                return ApplyResult(
                    PlannedOp(
                        tool="set_key_signature",
                        args=args,
                        status="error",
                        detail=f"Unknown key name '{name}'.",
                    )
                )
            fifths = KEY_NAME_TO_FIFTHS[name]
        measure = int(args.get("measure") or 1)
        self._push_undo()
        try:
            self.document.set_key_signature(fifths, measure)
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="set_key_signature",
                    args=args,
                    status="error",
                    detail=str(exc),
                )
            )
        return self._applied(
            PlannedOp(
                tool="set_key_signature",
                args={"fifths": fifths, "measure": measure},
                status="applied",
                detail=f"Set key signature fifths={fifths} at measure {measure}.",
            )
        )

    def _set_tempo(self, args: dict[str, Any]) -> ApplyResult:
        bpm = float(args["bpm"])
        measure = int(args.get("measure") or 1)
        self._push_undo()
        try:
            self.document.set_tempo(bpm, measure)
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(tool="set_tempo", args=args, status="error", detail=str(exc))
            )
        return self._applied(
            PlannedOp(
                tool="set_tempo",
                args={"bpm": bpm, "measure": measure},
                status="applied",
                detail=f"Set tempo ♩={bpm} at measure {measure}.",
            )
        )

    def _add_dynamic(self, args: dict[str, Any]) -> ApplyResult:
        marking = str(args["marking"])
        measure = int(args["measure"])
        self._push_undo()
        try:
            self.document.add_dynamic(
                marking,
                measure,
                beat=float(args.get("beat", 1.0)),
                staff_id=args.get("staff"),
            )
        except ValueError as exc:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(tool="add_dynamic", args=args, status="error", detail=str(exc))
            )
        return self._applied(
            PlannedOp(
                tool="add_dynamic",
                args=args,
                status="applied",
                detail=f"Added dynamic '{marking}' at measure {measure}.",
            )
        )

    def _set_lyrics(self, args: dict[str, Any]) -> ApplyResult:
        text = str(args["text"])
        measure = int(args["measure"])
        self._push_undo()
        n = self.document.set_lyrics(
            text,
            measure,
            beat=float(args.get("beat", 1.0)),
            verse=int(args.get("verse", 0)),
            staff_id=args.get("staff"),
        )
        if n == 0:
            self._abort_mutation()
            return ApplyResult(
                PlannedOp(
                    tool="set_lyrics",
                    args=args,
                    status="error",
                    detail="No note found to attach lyrics.",
                )
            )
        return self._applied(
            PlannedOp(
                tool="set_lyrics",
                args=args,
                status="applied",
                detail=f"Set lyrics on measure {measure}.",
            )
        )

    def _play_selection(self, args: dict[str, Any]) -> ApplyResult:
        args = {**args, "_tool": "play_selection"}
        sel = self._require_selection(args)
        if isinstance(sel, PlannedOp):
            sel.tool = "play_selection"
            return ApplyResult(sel)
        # Playback is a UI concern; tool returns applied instruction.
        return ApplyResult(
            PlannedOp(
                tool="play_selection",
                args={"selection": sel.model_dump(exclude_none=True)},
                status="applied",
                detail=(
                    f"Play measures {sel.measure_start}–{sel.measure_end} "
                    "(client should seek/play timeline range)."
                ),
            ),
            summary={
                **self.snapshot_summary(),
                "play": {
                    "measure_start": sel.measure_start,
                    "measure_end": sel.measure_end,
                },
            },
        )
