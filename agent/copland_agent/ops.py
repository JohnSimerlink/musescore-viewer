"""In-memory ops planner for score edit tools (no SVG re-render yet)."""

from __future__ import annotations

from typing import Any

from .models import PlannedOp, SelectionContext


def _sel_dict(selection: SelectionContext | None) -> dict[str, Any]:
    if selection is None:
        return {}
    return selection.model_dump(exclude_none=True)


def plan_transpose(
    semitones: int,
    selection: SelectionContext | None = None,
) -> PlannedOp:
    if selection is None or selection.measure_start is None:
        return PlannedOp(
            tool="transpose_selection",
            args={"semitones": semitones},
            status="error",
            detail="No measure selection provided.",
        )
    return PlannedOp(
        tool="transpose_selection",
        args={"semitones": semitones, "selection": _sel_dict(selection)},
        status="planned",
        detail=(
            f"Would transpose measures {selection.measure_start}–{selection.measure_end} "
            f"by {semitones:+d} semitone(s)."
        ),
    )


def plan_delete(selection: SelectionContext | None = None) -> PlannedOp:
    if selection is None or selection.measure_start is None:
        return PlannedOp(
            tool="delete_selection",
            args={},
            status="error",
            detail="No measure selection provided.",
        )
    return PlannedOp(
        tool="delete_selection",
        args={"selection": _sel_dict(selection)},
        status="planned",
        detail=(
            f"Would delete content in measures {selection.measure_start}–{selection.measure_end}."
        ),
    )


def plan_duplicate(
    measure_start: int,
    measure_end: int,
    insert_after: int | None = None,
) -> PlannedOp:
    if measure_start < 1 or measure_end < measure_start:
        return PlannedOp(
            tool="duplicate_measures",
            args={
                "measure_start": measure_start,
                "measure_end": measure_end,
                "insert_after": insert_after,
            },
            status="error",
            detail="Invalid measure range.",
        )
    target = insert_after if insert_after is not None else measure_end
    return PlannedOp(
        tool="duplicate_measures",
        args={
            "measure_start": measure_start,
            "measure_end": measure_end,
            "insert_after": target,
        },
        status="planned",
        detail=f"Would clone measures {measure_start}–{measure_end} after measure {target}.",
    )


def plan_set_duration(
    duration: str,
    selection: SelectionContext | None = None,
) -> PlannedOp:
    allowed = {
        "whole",
        "half",
        "quarter",
        "eighth",
        "sixteenth",
        "32nd",
        "dotted-half",
        "dotted-quarter",
        "dotted-eighth",
    }
    if duration not in allowed:
        return PlannedOp(
            tool="set_note_duration",
            args={"duration": duration},
            status="error",
            detail=f"Unsupported duration '{duration}'.",
        )
    return PlannedOp(
        tool="set_note_duration",
        args={"duration": duration, "selection": _sel_dict(selection)},
        status="planned",
        detail=(
            f"Would set note durations to {duration}"
            + (
                f" in measures {selection.measure_start}–{selection.measure_end}."
                if selection and selection.measure_start is not None
                else " for the current selection / caret."
            )
        ),
    )


def plan_set_selection(
    measure_start: int,
    measure_end: int,
    voices: list[str] | None = None,
    staves: list[str] | None = None,
) -> PlannedOp:
    if measure_start < 1 or measure_end < measure_start:
        return PlannedOp(
            tool="set_selection",
            args={"measure_start": measure_start, "measure_end": measure_end},
            status="error",
            detail="Invalid measure range.",
        )
    return PlannedOp(
        tool="set_selection",
        args={
            "measure_start": measure_start,
            "measure_end": measure_end,
            "voices": voices or [],
            "staves": staves or [],
        },
        status="stub",
        detail=(
            f"Selection context noted: measures {measure_start}–{measure_end}"
            + (f", voices={voices}" if voices else "")
            + (f", staves={staves}" if staves else "")
            + "."
        ),
    )
