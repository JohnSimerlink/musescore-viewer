"""Smoke tests for production agent/session path (no MuseScore CLI required)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from copland_agent.main import app
from copland_agent.sessions import SessionStore, default_seed_dir


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "public" / "seed"


def test_default_seed_dir_points_at_repo_seed():
    assert default_seed_dir().resolve() == SEED.resolve()
    assert (SEED / "catalog.json").is_file()


def test_session_open_and_apply_mutates_score():
    store = SessionStore(seed_dir=SEED)
    sess = store.get_or_open("dance-with-you", title="Dance")
    assert sess.engine.revision == 0
    result = sess.apply(
        "transpose_selection",
        {"semitones": 1, "selection": {"measure_start": 1, "measure_end": 2}},
        render=True,
    )
    assert result.op.status == "applied"
    assert sess.engine.revision == 1
    assets = sess.public_assets()
    assert assets["slug"] == "dance-with-you"
    assert assets["render"]["mode"] in {"musescore", "unavailable", "error", "none"}



def test_agent_health_and_session_open_http():
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["ok"] is True
    assert body["service"] == "copland-agent"

    opened = client.post("/api/session/open", json={"score_slug": "winter-wonderland"})
    assert opened.status_code == 200
    data = opened.json()
    assert data["slug"] == "winter-wonderland"
    assert "revision" in data

    applied = client.post(
        "/api/session/apply",
        json={
            "score_slug": "winter-wonderland",
            "tool": "transpose_selection",
            "args": {"semitones": -1},
            "selection": {"measure_start": 1, "measure_end": 1},
        },
    )
    assert applied.status_code == 200
    payload = applied.json()
    assert payload["op"]["status"] == "applied"
    assert payload["score_assets"]["revision"] >= 1


def test_start_prod_script_exists():
    script = ROOT / "scripts" / "start-prod.sh"
    assert script.is_file()
    text = script.read_text()
    assert "copland_agent" in text
    assert "server.mjs" in text
    assert "COPLAND_SEED_DIR" in text
