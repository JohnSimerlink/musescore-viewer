from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)

from .models import ChatMessage, SelectionContext
from .tools import AgentDeps, register_tools

_AGENT_DIR = Path(__file__).resolve().parents[1]
_ROOT = _AGENT_DIR.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local")
load_dotenv(_AGENT_DIR / ".env")
load_dotenv(_AGENT_DIR / ".env.local")

SYSTEM_PROMPT = """You are Copland, a score-editing assistant for composers.

You help users edit sheet music via structured tools that mirror clickable UI actions.
The browser currently shows pre-rendered MuseScore SVG pages; tools return planned
operations rather than mutating a live document. Be concise and practical.

When the user attaches a selection (measures / voices / staves), prefer tools that
operate on that selection. If they say "this" or "all this", use the attached selection.
If a required selection is missing, ask for measures or call set_selection.

Available tools include: transpose_selection, delete_selection, duplicate_measures,
set_note_duration, set_selection, clear_selection.

After calling tools, briefly summarize what you planned. Do not invent notation that
was not requested.
"""


def llm_provider() -> str:
    return (os.environ.get("LLM_PROVIDER") or "xai").strip().lower()


def llm_model_id() -> str:
    return (os.environ.get("LLM_MODEL") or "grok-4.5").strip()


def api_key_present() -> bool:
    provider = llm_provider()
    if provider == "xai":
        return bool(os.environ.get("XAI_API_KEY") or os.environ.get("COPLAND_API_KEY"))
    if provider == "openai":
        return bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("COPLAND_API_KEY"))
    return bool(
        os.environ.get("XAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("COPLAND_API_KEY")
    )


def model_name() -> str:
    """PydanticAI model string, e.g. xai:grok-4.5."""
    provider = llm_provider()
    model = llm_model_id()
    if ":" in model:
        return model
    return f"{provider}:{model}"


def build_model():
    """Build a provider-aware model object when extras are needed."""
    provider = llm_provider()
    model_id = llm_model_id()
    if provider == "xai":
        from pydantic_ai.models.xai import XaiModel
        from pydantic_ai.providers.xai import XaiProvider

        api_key = os.environ.get("XAI_API_KEY") or os.environ.get("COPLAND_API_KEY")
        api_host = os.environ.get("XAI_BASE_URL") or os.environ.get("XAI_API_HOST")
        provider_kwargs: dict[str, Any] = {}
        if api_key:
            provider_kwargs["api_key"] = api_key
        if api_host:
            provider_kwargs["api_host"] = api_host
        return XaiModel(model_id, provider=XaiProvider(**provider_kwargs))
    # Fallback: let Agent resolve openai:… etc.
    return model_name()


def build_agent() -> Agent[AgentDeps, str]:
    agent: Agent[AgentDeps, str] = Agent(
        build_model(),
        deps_type=AgentDeps,
        system_prompt=SYSTEM_PROMPT,
        retries=1,
    )
    register_tools(agent)
    return agent


def history_to_messages(history: list[ChatMessage]) -> list[ModelMessage]:
    messages: list[ModelMessage] = []
    for msg in history:
        text = (msg.content or "").strip()
        if not text:
            continue
        if msg.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=text)]))
        elif msg.role == "assistant":
            messages.append(ModelResponse(parts=[TextPart(content=text)]))
    return messages


def selection_block(selection: SelectionContext | None) -> str:
    if selection is None:
        return "Selection: (none)"
    parts = []
    if selection.measure_start is not None:
        end = selection.measure_end if selection.measure_end is not None else selection.measure_start
        parts.append(f"measures {selection.measure_start}–{end}")
    if selection.voices:
        parts.append("voices=" + ",".join(selection.voices))
    if selection.staves:
        parts.append("staves=" + ",".join(selection.staves))
    if selection.label:
        parts.append(f'label="{selection.label}"')
    if selection.elids:
        parts.append(f"elids={len(selection.elids)}")
    return "Selection: " + ("; ".join(parts) if parts else "(empty)")


def build_user_prompt(
    message: str,
    *,
    score_slug: str | None,
    score_title: str | None,
    selection: SelectionContext | None,
) -> str:
    score_line = "Score: "
    if score_title or score_slug:
        score_line += f"{score_title or score_slug}"
        if score_slug and score_title:
            score_line += f" ({score_slug})"
    else:
        score_line += "(none loaded)"
    return (
        f"{score_line}\n"
        f"{selection_block(selection)}\n\n"
        f"User command:\n{message.strip()}"
    )


def extract_tool_calls(messages: list[ModelMessage]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    for msg in messages:
        for part in getattr(msg, "parts", []) or []:
            ptype = getattr(part, "part_kind", None) or type(part).__name__
            if ptype in ("tool-call", "ToolCallPart"):
                tool_name = getattr(part, "tool_name", None)
                args = getattr(part, "args", None)
                if isinstance(args, str):
                    arg_payload: Any = {"raw": args}
                elif isinstance(args, dict):
                    arg_payload = args
                else:
                    arg_payload = {}
                tool_call_id = getattr(part, "tool_call_id", None) or str(len(pending))
                pending[tool_call_id] = {
                    "name": tool_name or "unknown",
                    "args": arg_payload if isinstance(arg_payload, dict) else {},
                    "result": {},
                }
            elif ptype in ("tool-return", "ToolReturnPart"):
                tool_call_id = getattr(part, "tool_call_id", None)
                content = getattr(part, "content", None)
                result = content if isinstance(content, dict) else {"content": content}
                if tool_call_id and tool_call_id in pending:
                    pending[tool_call_id]["result"] = result
                    records.append(pending.pop(tool_call_id))
                else:
                    records.append(
                        {
                            "name": getattr(part, "tool_name", "unknown"),
                            "args": {},
                            "result": result,
                        }
                    )
    records.extend(pending.values())
    return records
