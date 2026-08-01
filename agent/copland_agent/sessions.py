"""In-memory per-score edit sessions."""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .apply.engine import ApplyEngine, ApplyResult
from .models import PlannedOp
from .render.musescore_cli import RenderResult, find_mscore, render_score
from .score.load import load_score, resolve_seed_score_path


def default_seed_dir() -> Path:
    env = os.environ.get("COPLAND_SEED_DIR")
    if env:
        return Path(env)
    # agent/copland_agent/sessions.py → repo root / public/seed
    return Path(__file__).resolve().parents[2] / "public" / "seed"


@dataclass
class ScoreSession:
    slug: str
    engine: ApplyEngine
    title: str | None = None
    render_dir: Path | None = None
    last_render: RenderResult | None = None
    auto_render: bool = True

    def apply(
        self,
        tool: str,
        args: dict[str, Any] | None = None,
        *,
        render: bool | None = None,
    ) -> ApplyResult:
        result = self.engine.apply(tool, args)
        should_render = self.auto_render if render is None else render
        if (
            should_render
            and result.op.status == "applied"
            and tool
            not in {
                "set_selection",
                "clear_selection",
                "set_selection_voices",
                "copy_selection",
                "play_selection",
                "label_version",
            }
        ):
            self.render(include_audio=False)
        return result

    def render(self, *, include_audio: bool = False) -> RenderResult:
        if self.render_dir is None:
            self.render_dir = Path(tempfile.mkdtemp(prefix=f"copland-{self.slug}-"))
        else:
            # clean previous pages
            for p in self.render_dir.glob("page-*.svg"):
                p.unlink(missing_ok=True)
        result = render_score(
            self.engine.document,
            self.render_dir,
            include_audio=include_audio,
        )
        self.last_render = result
        return result

    def public_assets(self) -> dict[str, Any]:
        rev = self.engine.revision
        base = f"/api/session/{self.slug}/assets"
        pages = []
        if self.last_render and self.last_render.ok:
            pages = [f"{base}/{name}?v={rev}" for name in self.last_render.pages]
        return {
            "slug": self.slug,
            "revision": rev,
            "summary": self.engine.snapshot_summary(),
            "can_undo": self.engine.can_undo(),
            "can_redo": self.engine.can_redo(),
            "history": self.engine.log.public_history(),
            "selection": self.engine.selection.model_dump() if self.engine.selection else None,
            "render": {
                "ok": bool(self.last_render and self.last_render.ok),
                "mode": self.last_render.mode if self.last_render else "none",
                "detail": self.last_render.detail if self.last_render else None,
                "pages": pages,
                "timeline_url": f"{base}/timeline.json?v={rev}"
                if self.last_render and self.last_render.timeline
                else None,
                "audio_url": f"{base}/audio.mp3?v={rev}"
                if self.last_render and self.last_render.audio_name
                else None,
                "mscore_available": find_mscore() is not None,
            },
        }


@dataclass
class SessionStore:
    seed_dir: Path = field(default_factory=default_seed_dir)
    sessions: dict[str, ScoreSession] = field(default_factory=dict)

    def get_or_open(self, slug: str, *, title: str | None = None) -> ScoreSession:
        if slug in self.sessions:
            sess = self.sessions[slug]
            if title:
                sess.title = title
            return sess
        path = resolve_seed_score_path(self.seed_dir, slug)
        doc = load_score(path)
        engine = ApplyEngine(doc)
        sess = ScoreSession(slug=slug, engine=engine, title=title)
        self.sessions[slug] = sess
        return sess

    def get(self, slug: str) -> ScoreSession | None:
        return self.sessions.get(slug)

    def reset(self, slug: str) -> ScoreSession:
        old = self.sessions.pop(slug, None)
        if old and old.render_dir and old.render_dir.exists():
            shutil.rmtree(old.render_dir, ignore_errors=True)
        return self.get_or_open(slug, title=old.title if old else None)


STORE = SessionStore()
