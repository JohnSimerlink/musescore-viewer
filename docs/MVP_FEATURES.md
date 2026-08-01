# Copland MVP Features

Editing parity target: basic MuseScore-style score editing, with natural-language tools as first-class peers to click UI.

Status key:

- **planned** — schema + agent tool stub; no live score mutation yet
- **scaffold** — selection / ops model / API loop works; visual re-render deferred
- **real** — wired end-to-end against the current seed viewer

---

## Must-have for MVP

Click UI and agent tools should expose the same operations.

| Feature | Click UI | Agent tool | Status |
| --- | --- | --- | --- |
| Select measures / region | Drag or shift-click measures on SVG | `set_selection` | scaffold (measure geometry from timeline) |
| Clear selection | Esc / Clear | `clear_selection` | scaffold |
| Transpose selection | Transpose palette | `transpose_selection` | scaffold (planned ops) |
| Delete selection | Delete / Backspace | `delete_selection` | scaffold (planned ops) |
| Duplicate / clone measures | Copy + paste after | `duplicate_measures` | scaffold (planned ops) |
| Change note duration | Duration toolbar | `set_note_duration` | planned |
| Add note at caret | Note input mode + pitch | `add_note` | planned |
| Delete note / rest | Delete with note selected | `delete_note` | planned |
| Insert rest | Rest input | `add_rest` | planned |
| Copy selection | Cmd/Ctrl+C | `copy_selection` | planned |
| Cut selection | Cmd/Ctrl+X | `cut_selection` | planned |
| Paste at target | Cmd/Ctrl+V | `paste_selection` | planned |
| Insert measure(s) | Measure insert | `insert_measures` | planned |
| Delete measure(s) | Measure delete | `delete_measures` | planned |
| Set time signature | Inspector / palette | `set_time_signature` | planned |
| Set key signature | Inspector / palette | `set_key_signature` | planned |
| Set tempo | Tempo text / inspector | `set_tempo` | planned |
| Add dynamic | Dynamics palette | `add_dynamic` | planned |
| Edit / add lyrics | Lyrics mode | `set_lyrics` | planned |
| Undo / redo | Cmd/Ctrl+Z / Shift+Z | `undo`, `redo` | planned |
| Play / seek selection | Transport + click seek | `play_selection` | real seek exists; tool planned |
| Voice / staff filter on selection | Staff picker | `set_selection_voices` | planned |

### Tool schemas (MVP stubs)

```text
set_selection(measure_start, measure_end, voices?, staves?)
clear_selection()
transpose_selection(semitones, selection?)
delete_selection(selection?)
duplicate_measures(measure_start, measure_end, insert_after?)
set_note_duration(duration, selection?)   # e.g. "quarter" → "half"
add_note(pitch, duration, measure, beat, staff?, voice?)
delete_note(note_id | selection locator)
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
| Explain before apply | Agent returns planned ops + short confirmation | all tools (ops layer) |
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
| Live MSCZ round-trip | Parse/write MuseScore XML; re-export SVG + audio |
| Collaborative editing | CRDT / OT on ops log |
| MIDI / piano-roll hybrid | Pitch grid for dense edits |
| Optical music recognition import | PDF / photo → score |
| Plugin / scripting surface | Expose same tool registry |
| Offline local models | Optional non-OpenAI backends |

---

## Architecture notes (current phase)

1. **Seed viewer** serves pre-rendered SVG + timeline + MP3. There is no live MuseScore document in the browser yet.
2. **Selection** is measure-level, derived from timeline element geometry (`page`, `x`, `y`, `sx`, `sy`).
3. **Ops layer** validates structured operations and returns planned ops. Applying them to a JSON score model and re-rendering SVG comes next.
4. **Agent** (Python / PydanticAI) owns conversation history and the tool registry. Node serves the UI and proxies `/api/chat`.
5. Without `OPENAI_API_KEY`, the agent API returns a clear error; selection + command bar UX still work.
