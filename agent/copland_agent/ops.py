"""Plan + apply score edit tools against the active session."""

from __future__ import annotations

from typing import Any

from .models import PlannedOp, SelectionContext
from .sessions import STORE, ScoreSession


def _sel_dict(selection: SelectionContext | None) -> dict[str, Any]:
    if selection is None:
        return {}
    return selection.model_dump(exclude_none=True)


def resolve_session(score_slug: str | None) -> ScoreSession | None:
    if not score_slug:
        return None
    return STORE.get_or_open(score_slug)


def apply_tool(
    session: ScoreSession | None,
    tool: str,
    args: dict[str, Any],
) -> PlannedOp:
    if session is None:
        return PlannedOp(
            tool=tool,
            args=args,
            status="error",
            detail="No score loaded (missing score_slug).",
        )
    # Defer MuseScore re-render to end of chat / explicit API (faster multi-tool turns).
    result = session.apply(tool, args, render=False)
    return result.op


def plan_transpose(
    semitones: int,
    selection: SelectionContext | None = None,
    *,
    session: ScoreSession | None = None,
) -> PlannedOp:
    args: dict[str, Any] = {"semitones": semitones}
    if selection is not None:
        args["selection"] = selection
    return apply_tool(session, "transpose_selection", args)


def plan_delete(
    selection: SelectionContext | None = None,
    *,
    session: ScoreSession | None = None,
) -> PlannedOp:
    args: dict[str, Any] = {}
    if selection is not None:
        args["selection"] = selection
    return apply_tool(session, "delete_selection", args)


def plan_duplicate(
    measure_start: int,
    measure_end: int,
    insert_after: int | None = None,
    *,
    session: ScoreSession | None = None,
) -> PlannedOp:
    return apply_tool(
        session,
        "duplicate_measures",
        {
            "measure_start": measure_start,
            "measure_end": measure_end,
            "insert_after": insert_after,
        },
    )


def plan_set_duration(
    duration: str,
    selection: SelectionContext | None = None,
    *,
    session: ScoreSession | None = None,
) -> PlannedOp:
    args: dict[str, Any] = {"duration": duration}
    if selection is not None:
        args["selection"] = selection
    return apply_tool(session, "set_note_duration", args)


def plan_set_selection(
    measure_start: int,
    measure_end: int,
    voices: list[str] | None = None,
    staves: list[str] | None = None,
    *,
    session: ScoreSession | None = None,
) -> PlannedOp:
    return apply_tool(
        session,
        "set_selection",
        {
            "measure_start": measure_start,
            "measure_end": measure_end,
            "voices": voices or [],
            "staves": staves or [],
        },
    )


def apply_named(
    session: ScoreSession | None,
    tool: str,
    **kwargs: Any,
) -> PlannedOp:
    return apply_tool(session, tool, kwargs)
