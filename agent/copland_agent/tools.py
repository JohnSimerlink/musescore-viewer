"""Tool registry for Copland score actions (apply against live session)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent, RunContext

from . import ops
from .models import PlannedOp, SelectionContext
from .sessions import STORE, ScoreSession


@dataclass
class AgentDeps:
    selection: SelectionContext | None = None
    score_slug: str | None = None
    score_title: str | None = None
    planned_ops: list[PlannedOp] = field(default_factory=list)
    session: ScoreSession | None = None

    def ensure_session(self) -> ScoreSession | None:
        if self.session is not None:
            return self.session
        if not self.score_slug:
            return None
        self.session = STORE.get_or_open(self.score_slug, title=self.score_title)
        if self.selection is not None:
            self.session.engine.selection = self.selection
        return self.session


def _effective_selection(
    ctx: RunContext[AgentDeps],
    selection: SelectionContext | None,
) -> SelectionContext | None:
    return selection if selection is not None else ctx.deps.selection


def _record(ctx: RunContext[AgentDeps], planned: PlannedOp) -> dict:
    ctx.deps.planned_ops.append(planned)
    if planned.tool == "set_selection" and planned.status == "applied":
        args = planned.args
        ctx.deps.selection = SelectionContext(
            measure_start=args.get("measure_start"),
            measure_end=args.get("measure_end"),
            voices=args.get("voices") or [],
            staves=args.get("staves") or [],
            label=f"Measures {args.get('measure_start')}–{args.get('measure_end')}",
        )
    if planned.tool == "clear_selection" and planned.status == "applied":
        ctx.deps.selection = None
    return planned.model_dump()


def register_tools(agent: Agent[AgentDeps, str]) -> None:
    @agent.tool
    def transpose_selection(
        ctx: RunContext[AgentDeps],
        semitones: int,
        selection: SelectionContext | None = None,
    ) -> dict:
        """Transpose the current (or provided) selection by semitones. Positive = up."""
        sess = ctx.deps.ensure_session()
        planned = ops.plan_transpose(
            semitones, _effective_selection(ctx, selection), session=sess
        )
        return _record(ctx, planned)

    @agent.tool
    def delete_selection(
        ctx: RunContext[AgentDeps],
        selection: SelectionContext | None = None,
    ) -> dict:
        """Delete notes/rests in the current (or provided) selection."""
        sess = ctx.deps.ensure_session()
        planned = ops.plan_delete(_effective_selection(ctx, selection), session=sess)
        return _record(ctx, planned)

    @agent.tool
    def duplicate_measures(
        ctx: RunContext[AgentDeps],
        measure_start: int,
        measure_end: int,
        insert_after: int | None = None,
    ) -> dict:
        """Clone a contiguous measure range and insert after a target measure."""
        sess = ctx.deps.ensure_session()
        planned = ops.plan_duplicate(
            measure_start, measure_end, insert_after, session=sess
        )
        return _record(ctx, planned)

    @agent.tool
    def set_note_duration(
        ctx: RunContext[AgentDeps],
        duration: str,
        selection: SelectionContext | None = None,
    ) -> dict:
        """Set note duration for the selection (e.g. quarter, half, eighth)."""
        sess = ctx.deps.ensure_session()
        planned = ops.plan_set_duration(
            duration, _effective_selection(ctx, selection), session=sess
        )
        return _record(ctx, planned)

    @agent.tool
    def set_selection(
        ctx: RunContext[AgentDeps],
        measure_start: int,
        measure_end: int,
        voices: list[str] | None = None,
        staves: list[str] | None = None,
    ) -> dict:
        """Record or update the logical score selection (measures / voices / staves)."""
        sess = ctx.deps.ensure_session()
        planned = ops.plan_set_selection(
            measure_start, measure_end, voices, staves, session=sess
        )
        return _record(ctx, planned)

    @agent.tool
    def clear_selection(ctx: RunContext[AgentDeps]) -> dict:
        """Clear the current score selection."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(sess, "clear_selection")
        return _record(ctx, planned)

    @agent.tool
    def add_note(
        ctx: RunContext[AgentDeps],
        pitch: int,
        duration: str,
        measure: int,
        beat: float = 1.0,
        staff: str | None = None,
        voice: int = 1,
    ) -> dict:
        """Add a note at a measure/beat location."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "add_note",
            pitch=pitch,
            duration=duration,
            measure=measure,
            beat=beat,
            staff=staff,
            voice=voice,
        )
        return _record(ctx, planned)

    @agent.tool
    def delete_note(
        ctx: RunContext[AgentDeps],
        measure: int | None = None,
        pitch: int | None = None,
        staff: str | None = None,
    ) -> dict:
        """Delete a note by measure/pitch (or first note in selection measure)."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess, "delete_note", measure=measure, pitch=pitch, staff=staff
        )
        return _record(ctx, planned)

    @agent.tool
    def add_rest(
        ctx: RunContext[AgentDeps],
        duration: str,
        measure: int,
        beat: float = 1.0,
        staff: str | None = None,
        voice: int = 1,
    ) -> dict:
        """Insert a rest at a measure/beat location."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "add_rest",
            duration=duration,
            measure=measure,
            beat=beat,
            staff=staff,
            voice=voice,
        )
        return _record(ctx, planned)

    @agent.tool
    def copy_selection(
        ctx: RunContext[AgentDeps],
        selection: SelectionContext | None = None,
    ) -> dict:
        """Copy the current selection to the clipboard."""
        sess = ctx.deps.ensure_session()
        args: dict[str, Any] = {}
        sel = _effective_selection(ctx, selection)
        if sel is not None:
            args["selection"] = sel
        planned = ops.apply_tool(sess, "copy_selection", args)
        return _record(ctx, planned)

    @agent.tool
    def cut_selection(
        ctx: RunContext[AgentDeps],
        selection: SelectionContext | None = None,
    ) -> dict:
        """Cut the current selection to the clipboard."""
        sess = ctx.deps.ensure_session()
        args: dict[str, Any] = {}
        sel = _effective_selection(ctx, selection)
        if sel is not None:
            args["selection"] = sel
        planned = ops.apply_tool(sess, "cut_selection", args)
        return _record(ctx, planned)

    @agent.tool
    def paste_selection(
        ctx: RunContext[AgentDeps],
        target: int,
    ) -> dict:
        """Paste clipboard after the given measure number (0 = beginning)."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(sess, "paste_selection", target=target)
        return _record(ctx, planned)

    @agent.tool
    def insert_measures(
        ctx: RunContext[AgentDeps],
        count: int,
        after_measure: int,
    ) -> dict:
        """Insert empty measures after a measure (0 = before first)."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess, "insert_measures", count=count, after_measure=after_measure
        )
        return _record(ctx, planned)

    @agent.tool
    def delete_measures(
        ctx: RunContext[AgentDeps],
        measure_start: int,
        measure_end: int,
    ) -> dict:
        """Delete a contiguous measure range."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "delete_measures",
            measure_start=measure_start,
            measure_end=measure_end,
        )
        return _record(ctx, planned)

    @agent.tool
    def set_time_signature(
        ctx: RunContext[AgentDeps],
        numerator: int,
        denominator: int,
        measure: int = 1,
    ) -> dict:
        """Set time signature starting at a measure."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "set_time_signature",
            numerator=numerator,
            denominator=denominator,
            measure=measure,
        )
        return _record(ctx, planned)

    @agent.tool
    def set_key_signature(
        ctx: RunContext[AgentDeps],
        fifths: int | None = None,
        name: str | None = None,
        measure: int = 1,
    ) -> dict:
        """Set key signature by circle-of-fifths integer or name (e.g. 'G', 'Bb')."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "set_key_signature",
            fifths=fifths,
            name=name,
            measure=measure,
        )
        return _record(ctx, planned)

    @agent.tool
    def set_tempo(
        ctx: RunContext[AgentDeps],
        bpm: float,
        measure: int = 1,
    ) -> dict:
        """Set tempo marking in BPM at a measure."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(sess, "set_tempo", bpm=bpm, measure=measure)
        return _record(ctx, planned)

    @agent.tool
    def add_dynamic(
        ctx: RunContext[AgentDeps],
        marking: str,
        measure: int,
        beat: float = 1.0,
        staff: str | None = None,
    ) -> dict:
        """Add a dynamic marking (p, mf, f, etc.) at a measure."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "add_dynamic",
            marking=marking,
            measure=measure,
            beat=beat,
            staff=staff,
        )
        return _record(ctx, planned)

    @agent.tool
    def set_lyrics(
        ctx: RunContext[AgentDeps],
        text: str,
        measure: int,
        beat: float = 1.0,
        verse: int = 0,
        staff: str | None = None,
    ) -> dict:
        """Set lyric text on the first note of a measure."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "set_lyrics",
            text=text,
            measure=measure,
            beat=beat,
            verse=verse,
            staff=staff,
        )
        return _record(ctx, planned)

    @agent.tool
    def undo(ctx: RunContext[AgentDeps]) -> dict:
        """Undo the last score edit."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(sess, "undo")
        return _record(ctx, planned)

    @agent.tool
    def redo(ctx: RunContext[AgentDeps]) -> dict:
        """Redo the last undone score edit."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(sess, "redo")
        return _record(ctx, planned)

    @agent.tool
    def play_selection(
        ctx: RunContext[AgentDeps],
        selection: SelectionContext | None = None,
    ) -> dict:
        """Ask the client to play the current selection range."""
        sess = ctx.deps.ensure_session()
        args: dict[str, Any] = {}
        sel = _effective_selection(ctx, selection)
        if sel is not None:
            args["selection"] = sel
        planned = ops.apply_tool(sess, "play_selection", args)
        return _record(ctx, planned)

    @agent.tool
    def set_selection_voices(
        ctx: RunContext[AgentDeps],
        voices: list[str] | None = None,
        staves: list[str] | None = None,
    ) -> dict:
        """Filter the current selection to specific voices/staves."""
        sess = ctx.deps.ensure_session()
        planned = ops.apply_named(
            sess,
            "set_selection_voices",
            voices=voices or [],
            staves=staves or [],
        )
        return _record(ctx, planned)
