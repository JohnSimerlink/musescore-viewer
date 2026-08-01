# Copland (MuseScore Viewer)

Frontend sheet viewer with seeded scores, audio playhead, measure selection, a bottom natural-language command bar, and an optional Python / PydanticAI agent (xAI Grok).

## Local (UI)

```bash
npm install
npm start
```

Open http://localhost:5177

## Agent (NL commands)

The Node server proxies `POST /api/chat` to a Python sidecar on port **5178**.

1. Copy env template and set your key:

```bash
cp .env.example .env
# edit .env — set XAI_API_KEY, LLM_PROVIDER=xai, LLM_MODEL=grok-4.5
```

2. In a second terminal:

```bash
npm run agent
```

3. Use the bottom command bar. Select measures with **Select** mode or **Shift+click**, then send a command like “move all this up a half step”.

Without an API key, the UI still works (selection + command bar); the agent returns a clear missing-key message.

### Env vars

| Variable | Purpose |
| --- | --- |
| `XAI_API_KEY` | xAI API key (required for Grok) |
| `LLM_PROVIDER` | `xai` (default) or `openai` |
| `LLM_MODEL` | e.g. `grok-4.5` |
| `XAI_BASE_URL` | optional OpenAI-compatible base URL |
| `COPLAND_AGENT_URL` | Node → agent URL (default `http://127.0.0.1:5178`) |

Never commit `.env`. Only `.env.example` is tracked.

## Dark mode

Header **Dark** / **Light** toggle. Preference is stored in `localStorage` (`copland-theme`); initial default follows `prefers-color-scheme`. Engraved score SVG pages stay light paper; app chrome follows the theme.

## MVP feature map

See [docs/MVP_FEATURES.md](docs/MVP_FEATURES.md) for must-have edit tools, NL differentiators, and later work.

## Re-seed scores

Requires MuseScore 4 CLI on macOS:

```bash
npm run seed
```

## Railway

Docker image serves the static UI + pre-rendered seed assets. The Python agent is an optional local sidecar for now (set secrets in Railway if you add an agent service later).
