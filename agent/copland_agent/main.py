from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .agent import (
    api_key_present,
    build_agent,
    build_user_prompt,
    extract_tool_calls,
    history_to_messages,
    llm_provider,
    model_name,
)
from .models import (
    ApplyRequest,
    ApplyResponse,
    ChatRequest,
    ChatResponse,
    ToolCallRecord,
)
from .render.musescore_cli import find_mscore
from .sessions import STORE
from .tools import AgentDeps

# Load repo-root .env first, then agent/.env (local overrides)
_AGENT_DIR = Path(__file__).resolve().parents[1]
_ROOT = _AGENT_DIR.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local")
load_dotenv(_AGENT_DIR / ".env")
load_dotenv(_AGENT_DIR / ".env.local")

app = FastAPI(title="Copland Agent", version="0.2.0")
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
        "mscore_available": find_mscore() is not None,
        "seed_dir": str(STORE.seed_dir),
        "open_sessions": list(STORE.sessions.keys()),
    }


@app.post("/api/session/open")
async def session_open(payload: dict):
    slug = payload.get("score_slug") or payload.get("slug")
    if not slug:
        raise HTTPException(400, "score_slug required")
    try:
        sess = STORE.get_or_open(slug, title=payload.get("score_title"))
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    if payload.get("render"):
        sess.render(include_audio=bool(payload.get("include_audio")))
    return sess.public_assets()


@app.post("/api/session/reset")
async def session_reset(payload: dict):
    slug = payload.get("score_slug") or payload.get("slug")
    if not slug:
        raise HTTPException(400, "score_slug required")
    sess = STORE.reset(slug)
    return sess.public_assets()


@app.get("/api/session/{slug}")
async def session_get(slug: str):
    sess = STORE.get(slug)
    if sess is None:
        try:
            sess = STORE.get_or_open(slug)
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from exc
    return sess.public_assets()


@app.post("/api/session/apply", response_model=ApplyResponse)
async def session_apply(req: ApplyRequest) -> ApplyResponse:
    try:
        sess = STORE.get_or_open(req.score_slug, title=req.score_title)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    if req.selection is not None:
        sess.engine.selection = req.selection
    args = dict(req.args)
    if req.selection is not None and "selection" not in args:
        args["selection"] = req.selection
    result = sess.apply(req.tool, args, render=True)
    return ApplyResponse(
        op=result.op,
        score_assets=sess.public_assets(),
        error=None if result.op.status != "error" else result.op.detail,
    )


@app.post("/api/session/{slug}/render")
async def session_render(slug: str, payload: dict | None = None):
    sess = STORE.get(slug)
    if sess is None:
        raise HTTPException(404, "Session not open")
    include_audio = bool((payload or {}).get("include_audio"))
    result = sess.render(include_audio=include_audio)
    return {"render": result.__dict__, "score_assets": sess.public_assets()}


@app.get("/api/session/{slug}/assets/{name}")
async def session_asset(slug: str, name: str):
    sess = STORE.get(slug)
    if sess is None or sess.render_dir is None:
        raise HTTPException(404, "No rendered assets")
    # prevent path traversal
    safe = Path(name).name
    path = sess.render_dir / safe
    if not path.exists():
        raise HTTPException(404, "Asset not found")
    return FileResponse(path)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    session = None
    if req.score_slug:
        try:
            session = STORE.get_or_open(req.score_slug, title=req.score_title)
            if req.selection is not None:
                session.engine.selection = req.selection
        except FileNotFoundError:
            session = None

    if not api_key_present():
        provider = llm_provider()
        key_hint = "XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY"
        return ChatResponse(
            reply=(
                f"No model API key configured. Set {key_hint} in the repo-root .env "
                "(see .env.example), then restart the agent. Selection and the command "
                "bar still work offline; use click tools /api/session/apply for edits."
            ),
            selection=req.selection,
            error="missing_api_key",
            model=None,
            score_assets=session.public_assets() if session else None,
        )

    deps = AgentDeps(
        selection=req.selection,
        score_slug=req.score_slug,
        score_title=req.score_title,
        session=session,
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
            score_assets=session.public_assets() if session else None,
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

    active = deps.session or session
    assets = None
    if active is not None:
        # Re-render once after the full tool turn when MuseScore is available.
        if any(op.status == "applied" for op in deps.planned_ops):
            active.render(include_audio=False)
        assets = active.public_assets()

    return ChatResponse(
        reply=str(result.output),
        tool_calls=tool_records,
        planned_ops=deps.planned_ops,
        selection=deps.selection or req.selection,
        model=model_name(),
        error=None,
        score_assets=assets,
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
