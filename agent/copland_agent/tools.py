"""Tool registry for Copland score actions."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai import Agent, RunContext

from . import ops
from .models import PlannedOp, SelectionContext


@dataclass
class AgentDeps:
    selection: SelectionContext | None = None
    score_slug: str | None = None
    score_title: str | None = None
    planned_ops: list[PlannedOp] = field(default_factory=list)


def _effective_selection(
    ctx: RunContext[AgentDeps],
    selection: SelectionContext | None,
) -> SelectionContext | None:
    return selection if selection is not None else ctx.deps.selection


def register_tools(agent: Agent[AgentDeps, str]) -> None:
    @agent.tool
    def transpose_selection(
        ctx: RunContext[AgentDeps],
        semitones: int,
        selection: SelectionContext | None = None,
    ) -> dict:
        """Transpose the current (or provided) selection by semitones. Positive = up."""
        planned = ops.plan_transpose(semitones, _effective_selection(ctx, selection))
        ctx.deps.planned_ops.append(planned)
        return planned.model_dump()

    @agent.tool
    def delete_selection(
        ctx: RunContext[AgentDeps],
        selection: SelectionContext | None = None,
    ) -> dict:
        """Delete notes/rests in the current (or provided) selection."""
        planned = ops.plan_delete(_effective_selection(ctx, selection))
        ctx.deps.planned_ops.append(planned)
        return planned.model_dump()

    @agent.tool
    def duplicate_measures(
        ctx: RunContext[AgentDeps],
        measure_start: int,
        measure_end: int,
        insert_after: int | None = None,
    ) -> dict:
        """Clone a contiguous measure range and insert after a target measure."""
        planned = ops.plan_duplicate(measure_start, measure_end, insert_after)
        ctx.deps.planned_ops.append(planned)
        return planned.model_dump()

    @agent.tool
    def set_note_duration(
        ctx: RunContext[AgentDeps],
        duration: str,
        selection: SelectionContext | None = None,
    ) -> dict:
        """Set note duration for the selection (e.g. quarter, half, eighth)."""
        planned = ops.plan_set_duration(duration, _effective_selection(ctx, selection))
        ctx.deps.planned_ops.append(planned)
        return planned.model_dump()

    @agent.tool
    def set_selection(
        ctx: RunContext[AgentDeps],
        measure_start: int,
        measure_end: int,
        voices: list[str] | None = None,
        staves: list[str] | None = None,
    ) -> dict:
        """Record or update the logical score selection (measures / voices / staves)."""
        planned = ops.plan_set_selection(measure_start, measure_end, voices, staves)
        ctx.deps.planned_ops.append(planned)
        if planned.status != "error":
            ctx.deps.selection = SelectionContext(
                measure_start=measure_start,
                measure_end=measure_end,
                voices=voices or [],
                staves=staves or [],
                label=f"Measures {measure_start}–{measure_end}",
            )
        return planned.model_dump()

    @agent.tool
    def clear_selection(ctx: RunContext[AgentDeps]) -> dict:
        """Clear the current score selection."""
        ctx.deps.selection = None
        planned = PlannedOp(
            tool="clear_selection",
            args={},
            status="stub",
            detail="Selection cleared in agent context.",
        )
        ctx.deps.planned_ops.append(planned)
        return planned.model_dump()
