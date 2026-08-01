# MuseScore Viewer

Frontend-only sheet viewer with seeded scores, audio playback, and a clickable playhead.

## Local

```bash
npm install
npm start
```

Open http://localhost:5177

## Re-seed scores

Requires MuseScore 4 CLI on macOS:

```bash
npm run seed
```

## Railway

Docker image serves the static UI + pre-rendered seed assets (SVG, MP3, timeline). No MuseScore runtime needed in production.
