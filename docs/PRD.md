# Copland Product Requirements

Copland is an NL-first sheet music editor/viewer: Open Fanfare visual language (light paper / navy / brass / copper playhead), with dark mode. Natural-language tools are first-class peers to click UI.

This document is the product roadmap. MVP feature status lives in [MVP_FEATURES.md](./MVP_FEATURES.md). Edit-loop plan: [plans/mvp-edit-loop.md](./plans/mvp-edit-loop.md).

---

## Product pillars

1. **See the score** — engraved pages + playhead stay primary.
2. **Talk to edit** — NL agent applies the same ops as click tools.
3. **Mutation history** — every edit is an undo-able event; history is the substrate for versions and collaboration.
4. **Device-appropriate shells** — desktop right-rail agent; mobile score-first with bottom chat.

---

## Ships in current MVP

- Seed SVG/MP3/timeline playback, catalog, measure selection, NL agent (Grok).
- Mutable MSCX score session; apply layer with **mutation event log** (linear undo/redo, hop-to-state, optional named labels).
- Full MVP tool registry (applied, not stubs); click toolbar for selection-scoped ops.
- Re-render via MuseScore CLI when available; seed SVG fallback otherwise.
- **Desktop:** scores sidebar + main stage + NL **right rail**.
- **Mobile shell:** score-first viewport; library as drawer/screen; compact transport; bottom NL dock; fullscreen chat with back-to-score; touch-friendly Select mode.

---

## Information architecture (UX)

```text
Library  ←→  Score (primary)  ←→  Chat fullscreen
                ↕
         Bottom chat dock (mobile)
         Right rail (desktop)
```

| Surface | Desktop | Mobile |
| --- | --- | --- |
| Library / scores | Left sidebar | Drawer or dedicated library view (not permanently stacked above the score) |
| Score | Center stage | Full primary viewport when a score is open |
| Transport | Slim bar above score | Compact chrome over/near score or slim strip above chat |
| NL chat | Right rail (always visible) | Compact bottom dock by default; Expand → chat-only fullscreen; **← Score** returns |

Touch: Select mode for tap/range; long-press may enter select; do not rely on Shift+click alone.

---

## Mutation tree, versions, and branching (product model)

### Intended model (git-like songs)

Users can version and branch songs similarly to git: alternate arrangements live on branches; named versions (e.g. `"v3.1"`) label memorable states; hopping between states is first-class.

### Mutation-tree history (foundation — lands with MVP apply layer)

- Every score edit is stored as an **undo-able mutation** in an append-only / tree-friendly **event log**.
- Every state can be **fast-forwarded / hopped to** by mutation id (or index along the current spine).
- At any time a user can **label** the current state as a named version.
- New edits after undo append with `parent = current` (tree-friendly); MVP UI exposes linear undo/redo + hop/label APIs; full branch UX can come later.
- Design implication: prefer mutation log over a disposable linear stack that loses alternate futures.

### What ships now vs later

| Capability | MVP | Later |
| --- | --- | --- |
| Append-only mutation log + snapshots | Yes | — |
| Linear undo / redo | Yes | — |
| Hop to mutation id / index | Yes (API / session) | Polished timeline UI |
| Label current state (`v3.1`) | Yes (API / session) | Version picker UI |
| Git-like branch UI / merge / compare | — | Yes |
| Persist versions to cloud / per-user repos | — | Yes |

---

## Real-time collaboration (Later)

- See other people's cursors / presence.
- All remote changes go through the **same mutation system** (mutation log is the collab transport substrate).
- Presence, conflict policy, and multiplayer sync are **post-MVP**. Do not block the local edit loop on full CRDT/OT.

---

## Later / roadmap (non-exhaustive)

See also [MVP_FEATURES.md](./MVP_FEATURES.md) Later table.

- Git-like branching UI for songs; version compare / merge.
- Realtime collab (cursors + shared mutation stream).
- MuseScore CLI worker for live SVG/audio re-render in production (agent already ships in the Docker image).
- Pitch keypad / inspector palettes for full click parity.
- Articulations, beaming, parts, mixer, OMR, offline models.

---

## Non-goals for current MVP PR

- Full multiplayer presence sync.
- Full git branching/merge UX.
- Guaranteeing MuseScore CLI inside Railway Docker.
