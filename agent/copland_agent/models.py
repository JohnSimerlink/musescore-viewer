from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SelectionContext(BaseModel):
    """Structured score selection attached to a chat turn."""

    measure_start: int | None = None
    measure_end: int | None = None
    voices: list[str] = Field(default_factory=list)
    staves: list[str] = Field(default_factory=list)
    elids: list[int] = Field(default_factory=list)
    page_indices: list[int] = Field(default_factory=list)
    label: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    message: str
    score_slug: str | None = None
    score_title: str | None = None
    selection: SelectionContext | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class PlannedOp(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: Literal["planned", "applied", "stub", "error"] = "planned"
    detail: str | None = None


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    planned_ops: list[PlannedOp] = Field(default_factory=list)
    selection: SelectionContext | None = None
    model: str | None = None
    error: str | None = None
    score_assets: dict[str, Any] | None = None


class ApplyRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    score_slug: str
    score_title: str | None = None
    selection: SelectionContext | None = None


class ApplyResponse(BaseModel):
    op: PlannedOp
    score_assets: dict[str, Any] | None = None
    error: str | None = None
