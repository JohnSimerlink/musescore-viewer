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

- **Desktop:** NL agent is a **right rail** (transcript + input + selection badge).
- **Mobile:** compact **bottom chat dock**; **Expand** opens fullscreen chat-only; **← Score** returns to the score with the bottom dock.

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

Docker image serves the static UI + pre-rendered seed assets. The Python agent and MuseScore CLI are **not** in the production image yet:

- Production remains seed playback + selection UI.
- Full edit + re-render loop is solid locally (`npm start` + `npm run agent` + MuseScore 4).
- Next deploy step: agent sidecar (with `XAI_API_KEY`) and optionally a MuseScore-enabled worker for SVG/audio re-render.
