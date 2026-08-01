# Copland (MuseScore Viewer)

Frontend sheet viewer with seeded scores, audio playhead, measure selection, click edit toolbar, and a natural-language agent (xAI Grok) that **applies** edits to a live in-memory MuseScore document.

## Local (UI)

```bash
npm install
npm start
```

Open http://localhost:5177

## Agent (NL commands + apply layer)

The Node server proxies `POST /api/chat` and `/api/session/*` to a Python sidecar on port **5178**.

1. Copy env template and set your key:

```bash
cp .env.example .env
# edit .env — set XAI_API_KEY, LLM_PROVIDER=xai, LLM_MODEL=grok-4.5
```

2. In a second terminal:

```bash
npm run agent
```

3. Select a score, select measures (**Select** mode or **Shift+click**), then either:
   - use the edit toolbar (transpose, duration, duplicate, undo/redo, …), or
   - send NL from the **Agent** panel, e.g. “select measures 4–6 and transpose up a half step”.

### Layout

- **Desktop:** scores sidebar + main stage + NL **right rail**.
- **Mobile (score-first shell):** library is a **drawer** (not stacked permanently); score fills the viewport; slim transport; compact **bottom chat dock**; **Expand** → fullscreen chat-only; **← Score** returns. Long-press a measure to enter/extend selection. Product IA: [docs/PRD.md](docs/PRD.md).

### Re-render after edits

If MuseScore 4 CLI is installed (macOS app path or `MSCORE_BIN`), the agent re-exports SVG + timeline after applied edits and the UI refreshes pages/playhead.

Without MuseScore CLI, edits still mutate the in-memory score (and tests cover this); the UI keeps seed SVG and shows a status note.

### Env vars

| Variable | Purpose |
| --- | --- |
| `XAI_API_KEY` | xAI API key (required for Grok chat) |
| `LLM_PROVIDER` | `xai` (default) or `openai` |
| `LLM_MODEL` | e.g. `grok-4.5` |
| `XAI_BASE_URL` / `XAI_API_HOST` | optional OpenAI-compatible / xAI host override |
| `COPLAND_AGENT_URL` | Node → agent URL (default `http://127.0.0.1:5178`) |
| `MSCORE_BIN` | Optional path to MuseScore CLI for live SVG re-render |
| `COPLAND_SEED_DIR` | Optional override for seed directory |

Never commit `.env`. Only `.env.example` is tracked.

### Tests

```bash
npm test
# or: cd agent && .venv/bin/pytest -q
```

## Dark mode

Header **Dark** / **Light** toggle. Preference is stored in `localStorage` (`copland-theme`); initial default follows `prefers-color-scheme`. Engraved score SVG pages stay light paper; app chrome follows the theme.

## MVP feature map

See [docs/MVP_FEATURES.md](docs/MVP_FEATURES.md) for must-have edit tools, NL differentiators, and later work.

## Re-seed scores

Requires MuseScore 4 CLI on macOS:

```bash
npm run seed
```

## Railway / production

The Docker image runs **Node UI + Python agent** in one container (`scripts/start-prod.sh`):

| Capability | In production image |
| --- | --- |
| Seed SVG / MP3 / timeline playback | Yes |
| NL chat + click apply (mutable MSCX) | Yes — set `XAI_API_KEY` (and optional `LLM_*`) on the Railway service |
| Live SVG/audio re-render after edits | No — MuseScore CLI is not in the image; UI keeps seed pages and shows a render-status note |

Set these Railway variables:

- `XAI_API_KEY` — required for Grok NL chat
- `LLM_PROVIDER=xai`, `LLM_MODEL=grok-4.5` (optional defaults match `.env.example`)
- `PORT` — Railway injects this; start script forwards it to Node

Local parity with the image:

```bash
# after npm install + agent venv (`npm run agent` once is enough to create .venv)
./scripts/start-prod.sh
```

Next deploy step: optional MuseScore-enabled worker/sidecar for live SVG/audio re-render.
