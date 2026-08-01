from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import (
    api_key_present,
    build_agent,
    build_user_prompt,
    extract_tool_calls,
    history_to_messages,
    llm_provider,
    model_name,
)
from .models import ChatRequest, ChatResponse, ToolCallRecord
from .tools import AgentDeps

# Load repo-root .env first, then agent/.env (local overrides)
_AGENT_DIR = Path(__file__).resolve().parents[1]
_ROOT = _AGENT_DIR.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local")
load_dotenv(_AGENT_DIR / ".env")
load_dotenv(_AGENT_DIR / ".env.local")

app = FastAPI(title="Copland Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = build_agent()
    return _agent


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "service": "copland-agent",
        "provider": llm_provider(),
        "model": model_name(),
        "api_key_configured": api_key_present(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    if not api_key_present():
        provider = llm_provider()
        key_hint = "XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY"
        return ChatResponse(
            reply=(
                f"No model API key configured. Set {key_hint} in the repo-root .env "
                "(see .env.example), then restart the agent. Selection and the command "
                "bar still work offline."
            ),
            selection=req.selection,
            error="missing_api_key",
            model=None,
        )

    deps = AgentDeps(
        selection=req.selection,
        score_slug=req.score_slug,
        score_title=req.score_title,
    )
    prompt = build_user_prompt(
        req.message,
        score_slug=req.score_slug,
        score_title=req.score_title,
        selection=req.selection,
    )
    history = history_to_messages(req.history)

    try:
        result = await get_agent().run(prompt, deps=deps, message_history=history)
    except Exception as exc:  # noqa: BLE001 — surface to client
        return ChatResponse(
            reply=f"Agent error: {exc}",
            selection=req.selection,
            error="agent_error",
            model=model_name(),
        )

    tool_records = [
        ToolCallRecord(name=r["name"], args=r.get("args") or {}, result=r.get("result") or {})
        for r in extract_tool_calls(result.new_messages())
    ]
    if not tool_records and deps.planned_ops:
        tool_records = [
            ToolCallRecord(name=op.tool, args=op.args, result=op.model_dump())
            for op in deps.planned_ops
        ]

    return ChatResponse(
        reply=str(result.output),
        tool_calls=tool_records,
        planned_ops=deps.planned_ops,
        selection=deps.selection or req.selection,
        model=model_name(),
        error=None,
    )


def run() -> None:
    import uvicorn

    host = os.environ.get("COPLAND_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("COPLAND_AGENT_PORT", "5178"))
    uvicorn.run(
        "copland_agent.main:app",
        host=host,
        port=port,
        reload=os.environ.get("COPLAND_AGENT_RELOAD") == "1",
    )


if __name__ == "__main__":
    run()
