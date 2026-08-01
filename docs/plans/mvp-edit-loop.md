# Plan: Copland MVP edit loop

## Goal

Ship a working natural-language + click edit loop for Copland: load a mutable score from seed MSCZ/MusicXML, apply MVP tools (transpose, delete, duration, duplicate, undo/redo, and the rest of the must-have registry), re-render SVG/timeline when MuseScore CLI is available, wire agent replies into the UI, and move the NL chat into a dedicated right rail — ending in a draft PR ready for human merge confirmation.

## Scope

**In**
- Mutable score model from seed MSCZ / MusicXML
- Apply layer with undo/redo; ops status `applied` (not stub/planned-only)
- Re-render pipeline (MuseScore 4 CLI when present; honest seed fallback when not)
- Agent tools → session apply → UI refresh
- Full MVP tool registry from `docs/MVP_FEATURES.md`
- Click UI parity for MVP click-expected ops
- Right-rail NL panel (desktop); mobile collapse/stack
- Focused unit/integration tests for apply layer + key tools
- Docs/README updates for local run + Railway limitations

**Out**
- Collaborative editing / CRDT
- Full articulations, beaming, linked parts
- Guaranteeing MuseScore CLI inside Railway Docker in this PR (document + design for later)
- Merging the PR without human confirmation

## Approach

1. **Score model** (`agent/copland_agent/score/`): unzip MSCZ → MSCX or load MusicXML; expose measure/note iterators and mutators.
2. **Session + apply** (`agent/copland_agent/session.py`, `apply/`): per-slug in-memory session, snapshot undo/redo, `apply_op` → `PlannedOp(status="applied")`.
3. **Render** (`agent/copland_agent/render/`): write MusicXML/MSCX temp → MuseScore CLI → SVG pages + timeline (+ optional audio); expose `/api/session/*` from agent; Node proxies.
4. **Tools**: replace stubs in `tools.py` / `ops.py` with real apply calls; register remaining MVP tools.
5. **UI**: right-rail agent panel; edit toolbar (transpose, duration, duplicate, undo/redo, etc.); on chat/apply, refresh pages from render revision URL.
6. **Seed**: ensure `score.musicxml` (or extractable MSCX) available; update `prepare-seed.sh` to export MusicXML.
7. **Tests**: pytest for parse/apply/undo/tools; CI workflow if none exists.
8. **Docs**: update `MVP_FEATURES.md` statuses; README local + Railway notes.

## Acceptance Criteria

- [ ] Mutable score model loaded from seed MSCZ/MusicXML — evidence: `test_load_seed_score` / session open returns measure count
- [ ] Transpose, delete selection, set duration, duplicate measures APPLY and change the score — evidence: apply-layer tests + ops `status=="applied"`
- [ ] Undo/redo works — evidence: `test_undo_redo_transpose`
- [ ] After apply, UI refreshes rendered score (SVG) and timeline/playhead still coherent — evidence: render endpoint returns new pages when CLI present; UI reloads revision; without CLI, documented fallback + model still mutates
- [ ] NL: “select m4–6 and transpose up a half step” results in applied transpose — evidence: integration test or manual local run note with `status=applied`
- [ ] Remaining MVP tools registered and applied (or clearly implemented with tests); no silent stubs for must-haves
- [ ] Click UI covers MVP click-parity items (or documented interim with justification)
- [ ] Right-rail NL layout on desktop; mobile collapse/stack — evidence: `index.html`/`styles.css` layout change
- [ ] Focused unit/integration tests for apply layer + key tools — evidence: `pytest` green
- [ ] Draft PR open; CI green; plan criteria checked; self-review finds nothing critical
- [ ] Do NOT merge without human confirmation

## Risks / Open Questions

- Railway image likely lacks MuseScore CLI → local E2E solid; prod stays seed SVG until sidecar/Docker with MuseScore. Document honestly.
- Soft decision: prefer MusicXML as editable interchange; keep MSCZ for CLI re-import when needed.
- Soft decision: snapshot-based undo (full XML) for MVP simplicity over inverse-ops.
- Soft decision: work on feature branch in main checkout if worktree attach fails (branch `auto/mvp-edit-loop`).
