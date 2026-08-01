# MuseScore Viewer

Localhost web UI for browsing and rendering `.mscz` / `.mscx` scores.

- Lists scores from `~/Documents/MuseScore4/Scores` and `~/Documents/incommon`
- Filter by **MuseScore 3 / 4 / Unknown**
- Renders via MuseScore CLI (default) with optional browser [webmscore](https://github.com/LibreScore/webmscore)
- **Play audio** exports MP3 through MuseScore CLI

## Requirements

- Node.js 18+
- MuseScore 3 or 4 installed (CLI used for reliable MS4 render + audio)

## Run

```bash
npm install
npm start
```

Open http://localhost:5177

## Notes

- webmscore often returns blank pages for MuseScore 4 files; Auto mode detects that and falls back to the CLI.
- Audio files are cached under your system temp dir (`msviewer-cache`).
