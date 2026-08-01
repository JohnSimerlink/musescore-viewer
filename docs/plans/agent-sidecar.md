# Plan: Production agent sidecar (Railway)

## Goal

Ship a production deploy path where the Copland Python agent runs alongside the Node UI so NL chat and click-apply work on Railway (mutations apply; SVG re-render still falls back when MuseScore CLI is absent).

## Scope

**In**
- Single Docker image runs Node UI + Python agent (same container)
- Start script: agent then Node; health waits for agent
- Env wiring: `COPLAND_AGENT_URL`, `COPLAND_SEED_DIR`, `XAI_API_KEY` / LLM vars
- `/api/health` reports agent reachability and deploy mode
- README / Railway notes for secrets and limitations
- Smoke test that agent boots against seed dir (no MuseScore required)

**Out**
- MuseScore CLI inside Docker / live SVG re-render in prod
- Separate Railway multi-service topology (document as optional later)
- Merging without human confirmation
- Changing MVP edit-loop behavior from PR #1

## Approach

1. Extend `Dockerfile` to install Python venv + agent deps; copy `agent/`.
2. Add `scripts/start-prod.sh` to launch uvicorn then `node server.mjs`.
3. Default prod env: agent on `127.0.0.1:5178`, seed at `/app/public/seed`.
4. Update `server.mjs` health `mode` when agent is up.
5. Pytest smoke: import app + resolve seed path; optional docker-compose note only.
6. Docs: README Railway section + `.env.example` if needed.

## Acceptance Criteria

- [x] Docker image defined with Node + agent (`Dockerfile` + `scripts/start-prod.sh`) — evidence: files in repo; local `docker build` blocked (daemon not running); Railway will build on deploy
- [x] Container/prod start serves UI on `$PORT` and agent on internal port — evidence: `PORT=5201` + agent `:5190` smoke via `start-prod.sh`
- [x] `/api/health` shows `agent.reachable: true` / `mode: "ui+agent"` when both up — evidence: curl smoke
- [x] `/api/session/open` with a seed slug succeeds without requiring MuseScore CLI success — evidence: curl + `test_agent_health_and_session_open_http`
- [x] Click/NL apply path works via proxy (apply without chat key still works) — evidence: curl apply `status=applied`; `test_session_open_and_apply_mutates_score`
- [x] README documents Railway env vars + MuseScore CLI still not in image — evidence: README Railway section
- [x] Focused test(s) for seed session open / health shape — evidence: `test_sidecar_smoke.py` (17 total pytest)
- [x] Draft PR stacked on `auto/mvp-edit-loop`; CI green
- [ ] Do NOT merge without human confirmation

## Risks / Open Questions

- Soft decision: one container (supervisor script) over two Railway services for MVP deploy simplicity.
- Soft decision: no MuseScore in image — mutations apply, seed SVG fallback remains.
- Soft decision: start script refuses if agent port already in use and requires current health shape (`seed_dir`, `mscore_available`) so a stale agent cannot pass the gate.
- Image size grows with Python deps; acceptable for this slice.
- Local Docker daemon was unavailable during implementation; verified via `npm start:prod` / `start-prod.sh` instead.
