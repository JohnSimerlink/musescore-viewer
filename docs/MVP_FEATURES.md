# Copland MVP Features

Editing parity target: basic MuseScore-style score editing, with natural-language tools as first-class peers to click UI.

Status key:

- **planned** — schema + agent tool stub; no live score mutation yet
- **scaffold** — selection / ops model / API loop works; visual re-render deferred
- **real** — wired end-to-end against the current seed viewer (mutations apply; SVG re-render when MuseScore CLI is present)

---

## Must-have for MVP

Click UI and agent tools should expose the same operations.

| Feature | Click UI | Agent tool | Status |
| --- | --- | --- | --- |
| Select measures / region | Drag or shift-click measures on SVG | `set_selection` | real |
| Clear selection | Esc / Clear | `clear_selection` | real |
| Transpose selection | Transpose ±1 toolbar | `transpose_selection` | real |
| Delete selection | Delete / Backspace | `delete_selection` | real |
| Duplicate / clone measures | Duplicate toolbar | `duplicate_measures` | real |
| Change note duration | Duration select + Set duration | `set_note_duration` | real |
| Add note at caret | (NL / apply API; no pitch keypad yet) | `add_note` | real (NL/API) |
| Delete note / rest | Delete selection covers chords | `delete_note` | real (NL/API) |
| Insert rest | (NL / apply API) | `add_rest` | real (NL/API) |
| Copy selection | Cmd/Ctrl+C + toolbar | `copy_selection` | real |
| Cut selection | Cmd/Ctrl+X + toolbar | `cut_selection` | real |
| Paste at target | Cmd/Ctrl+V + toolbar | `paste_selection` | real |
| Insert measure(s) | Insert bar toolbar | `insert_measures` | real |
| Delete measure(s) | Delete bars toolbar | `delete_measures` | real |
| Set time signature | (NL / apply API) | `set_time_signature` | real (NL/API) |
| Set key signature | (NL / apply API) | `set_key_signature` | real (NL/API) |
| Set tempo | (NL / apply API) | `set_tempo` | real (NL/API) |
| Add dynamic | (NL / apply API) | `add_dynamic` | real (NL/API) |
| Edit / add lyrics | (NL / apply API) | `set_lyrics` | real (NL/API) |
| Undo / redo | Cmd/Ctrl+Z / Shift+Z + toolbar | `undo`, `redo` | real |
| Play / seek selection | Play sel + click seek | `play_selection` | real |
| Voice / staff filter on selection | (NL / apply API) | `set_selection_voices` | real (NL/API) |

### Tool schemas (MVP — applied)

```text
set_selection(measure_start, measure_end, voices?, staves?)
clear_selection()
transpose_selection(semitones, selection?)
delete_selection(selection?)
duplicate_measures(measure_start, measure_end, insert_after?)
set_note_duration(duration, selection?)   # e.g. "quarter" → "half"
add_note(pitch, duration, measure, beat, staff?, voice?)
delete_note(measure?, pitch?, staff?)
add_rest(duration, measure, beat, staff?, voice?)
copy_selection() / cut_selection() / paste_selection(target)
insert_measures(count, after_measure)
delete_measures(measure_start, measure_end)
set_time_signature(numerator, denominator, measure?)
set_key_signature(fifths | name, measure?)
set_tempo(bpm, measure?)
add_dynamic(marking, measure, beat?, staff?)
set_lyrics(text, measure, beat?, verse?, staff?)
undo() / redo()
play_selection()
set_selection_voices(voices[], staves[])
```

Click-UI interim: pitch keypad / inspector for time/key/tempo/dynamics/lyrics remain NL/API-first; toolbar covers selection-scoped edit ops + clipboard + undo/redo + play selection. Documented conscious interim — agent parity is complete.

---

## NL / AI-first differentiators

These are where Copland should beat a click-only editor:

| Capability | Example utterance | Tools involved |
| --- | --- | --- |
| Region + verb | “move all this up a half step” (with measures 4–6 selected) | `transpose_selection` |
| Multi-step rewrite | “Clone measures 2–7 and make quarter notes half notes” | `duplicate_measures`, `set_note_duration` |
| Style paraphrase | “make the bass quieter in the chorus” | `add_dynamic`, `set_selection_voices` |
| Structural edit in prose | “repeat the intro after measure 16” | `duplicate_measures`, `insert_measures` |
| Lyric fill | “set verse 1 lyrics for measures 1–8 to …” | `set_lyrics` |
| Selection-aware defaults | Tools omit range when UI selection is attached | all selection-scoped tools |
| Explain before/after apply | Agent returns applied ops + short confirmation | all tools (ops layer) |
| Chat continuity | Follow-ups like “same thing but down a whole step” | conversation history |

---

## Later / nice-to-have

| Feature | Notes |
| --- | --- |
| Chord symbols / Roman numerals | Jazz / lead-sheet workflows |
| Articulations & ornaments | Slurs, ties, accents, trills |
| Beaming / tuplets | Complex rhythm editing |
| Parts / linked parts extraction | Conductor vs part views |
| Mixer / instrument changes | Playback routing |
| Live MSCZ round-trip on Railway | Docker image with MuseScore CLI for SVG/audio re-render |
| Git-like song branching UI | Branches / merge / compare — see [PRD.md](./PRD.md); mutation log is the substrate |
| Named version picker UI | Labels already supported on mutation log (`label_version` / hop) |
| Realtime collaboration | Cursors + shared mutation stream — see [PRD.md](./PRD.md) |
| MIDI / piano-roll hybrid | Pitch grid for dense edits |
| Optical music recognition import | PDF / photo → score |
| Plugin / scripting surface | Expose same tool registry |
| Offline local models | Optional non-OpenAI backends |
| Pitch keypad / inspector palettes | Full click parity for add_note / signatures / dynamics |

---

## Architecture notes (current phase)

1. **Mutable score model** loads seed `score.mscz` (MSCX inside zip) into an in-memory `ScoreDocument` on the Python agent.
2. **Apply layer** appends each edit to a **mutation event log** (tree-friendly: parent ids, hop-to-id, named labels) with document snapshots; linear undo/redo moves the head. Tool status is `applied` (not stub). See [PRD.md](./PRD.md) for versioning/collab intent.
3. **Re-render**: when MuseScore 4 CLI is available (`MSCORE_BIN` or macOS app path), applied edits export fresh SVG pages + timeline (+ optional audio). Without CLI, mutations still apply; UI keeps seed SVG and shows a render-status note.
4. **Selection** is measure-level in the browser, derived from timeline geometry; sent with chat / apply requests. Mobile: Select mode + long-press to start/extend ranges.
5. **Agent** (Python / PydanticAI) owns conversation history and the full MVP tool registry. Node serves the UI and proxies `/api/chat` + `/api/session/*`.
6. **UI shells**: desktop = library sidebar + score stage + NL **right rail**. Mobile = **score-first** (library drawer, compact transport, bottom chat dock, fullscreen chat). IA: Library ↔ Score ↔ Chat fullscreen.
7. **Railway / production**: Docker serves seed UI assets. Agent + MuseScore CLI are not in the production image yet — local `npm start` + `npm run agent` is the end-to-end edit path. Plan: agent sidecar and/or image with MuseScore for live re-render.

### Env vars

Without `XAI_API_KEY` (or `OPENAI_API_KEY`), the agent chat returns a clear error; click edit tools via `/api/session/apply` still work when the agent process is running.
