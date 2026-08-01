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

- [ ] Docker image builds with Node + agent (`docker build` succeeds locally or in CI when docker available)
- [ ] Container start serves UI on `$PORT` and agent on internal `:5178`
- [ ] `/api/health` shows `agent.reachable: true` when both processes up
- [ ] `/api/session/open` with a seed slug succeeds without MuseScore CLI
- [ ] Click/NL apply path works via proxy when `XAI_API_KEY` set (apply without key still works)
- [ ] README documents Railway env vars + MuseScore CLI still not in image
- [ ] Focused test(s) for seed session open / health shape
- [ ] Draft PR stacked on `auto/mvp-edit-loop`; CI green
- [ ] Do NOT merge without human confirmation

## Risks / Open Questions

- Soft decision: one container (supervisor script) over two Railway services for MVP deploy simplicity.
- Soft decision: no MuseScore in image — mutations apply, seed SVG fallback remains.
- Image size grows with Python deps; acceptable for this slice.
