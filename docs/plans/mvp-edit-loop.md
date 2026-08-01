# Plan: Copland MVP edit loop

## Goal

Ship a working natural-language + click edit loop for Copland: load a mutable score from seed MSCZ/MusicXML, apply MVP tools (transpose, delete, duration, duplicate, undo/redo, and the rest of the must-have registry), re-render SVG/timeline when MuseScore CLI is available, wire agent replies into the UI, and place NL chat in a desktop right rail / mobile bottom dock with fullscreen expand — ending in a draft PR ready for human merge confirmation.

## Scope

**In**
- Mutable score model from seed MSCZ / MusicXML
- Apply layer with undo/redo; ops status `applied` (not stub/planned-only)
- Re-render pipeline (MuseScore 4 CLI when present; honest seed fallback when not)
- Agent tools → session apply → UI refresh
- Full MVP tool registry from `docs/MVP_FEATURES.md`
- Click UI parity for MVP click-expected ops (toolbar + shortcuts; NL/API interim for inspector palettes)
- Desktop right-rail NL; mobile bottom dock + fullscreen chat with back-to-score
- Focused unit/integration tests for apply layer + key tools
- Docs/README updates for local run + Railway limitations

**Out**
- Collaborative editing / CRDT
- Full articulations, beaming, linked parts
- Guaranteeing MuseScore CLI inside Railway Docker in this PR (document + design for later)
- Merging the PR without human confirmation

## Approach

1. **Score model** (`agent/copland_agent/score/`): unzip MSCZ → MSCX; expose measure/note iterators and mutators.
2. **Session + apply** (`agent/copland_agent/sessions.py`, `apply/`): per-slug in-memory session, snapshot undo/redo, `apply_op` → `PlannedOp(status="applied")`.
3. **Render** (`agent/copland_agent/render/`): write MSCZ temp → MuseScore CLI → SVG pages + timeline (+ optional audio); expose `/api/session/*` from agent; Node proxies.
4. **Tools**: replace stubs with real apply calls; register remaining MVP tools.
5. **UI**: right-rail agent panel (desktop); mobile bottom dock + expand fullscreen; edit toolbar; on chat/apply, refresh pages from render revision URL.
6. **Tests**: pytest for parse/apply/undo/tools; GitHub Actions CI.
7. **Docs**: update `MVP_FEATURES.md` statuses; README local + Railway notes.

## Acceptance Criteria

- [x] Mutable score model loaded from seed MSCZ/MusicXML — evidence: `test_load_seed_score`, `test_load_mini_fixture`
- [x] Transpose, delete selection, set duration, duplicate measures APPLY and change the score — evidence: `test_transpose_applies`, `test_delete_selection_applies`, `test_set_duration_applies`, `test_duplicate_measures_applies` (`status=="applied"`)
- [x] Undo/redo works — evidence: `test_undo_redo_transpose`
- [x] After apply, UI refreshes rendered score (SVG) and timeline/playhead still coherent — evidence: `render/musescore_cli.py` + UI `applyScoreAssets`; without CLI, documented fallback + model still mutates
- [x] NL: “select m4–6 and transpose up a half step” results in applied transpose — evidence: `test_nl_style_select_and_transpose`
- [x] Remaining MVP tools registered and applied (or clearly implemented with tests); no silent stubs for must-haves — evidence: `test_remaining_mvp_tools_registered`, `test_no_silent_stub_for_transpose`
- [x] Click UI covers MVP click-parity items (or documented interim with justification) — evidence: edit toolbar + shortcuts; inspector palettes documented as NL/API interim in `MVP_FEATURES.md`
- [x] Right-rail NL on desktop; mobile bottom chat dock; mobile expand → fullscreen chat with back-to-score — evidence: `index.html` / `styles.css` / `app.js`
- [x] Focused unit/integration tests for apply layer + key tools — evidence: `npm test` → 12 passed
- [ ] Draft PR open; CI green; plan criteria checked; self-review finds nothing critical
- [ ] Do NOT merge without human confirmation

## Risks / Open Questions

- Railway image lacks MuseScore CLI → local E2E solid; prod stays seed SVG until sidecar/Docker with MuseScore. Documented in README.
- Soft decision: MSCX as editable representation (native seed format); MusicXML not required for MVP mutations.
- Soft decision: snapshot-based undo (full document clone) for MVP simplicity.
- Soft decision: work on feature branch `auto/mvp-edit-loop` in main checkout when worktree attach failed.
- Soft decision: click inspector palettes (pitch keypad, time/key/tempo/dynamics/lyrics) deferred to NL/API with documented interim.
