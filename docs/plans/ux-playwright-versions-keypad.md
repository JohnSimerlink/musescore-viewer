# Plan: Playwright UX loop + version picker + pitch keypad

## Goal

Add Playwright coverage for desktop/mobile shells, ship a named **version picker** on the mutation log, and a **pitch keypad / inspector** for click parity on add-note / signatures / dynamics / lyrics — then iterate on broken or unfriendly UX found in the browser.

## Scope

**In**
- Playwright e2e (local UI + agent): catalog load, select measures, transpose toolbar, agent rail/dock, mobile library drawer + chat expand
- Version picker UI: list labeled mutations, hop-to, label current (`label_version` / hop APIs)
- Pitch keypad + compact inspector palettes for time/key/tempo/dynamics/lyrics (click → `/api/session/apply`)
- UX fixes discovered while running Playwright
- Merge to main when CI green (user authorized autonomous merge)

**Out**
- MuseScore-in-Docker live re-render
- Realtime collab / full git branch merge UI
- Deploy (blocked until Railway auth is available in this environment)

## Approach

1. Add `@playwright/test`, smoke specs, `npm run test:e2e`, CI job (or optional).
2. Expose session history APIs already on `public_assets().history`; wire Version UI in edit chrome.
3. Add keypad/inspector panel; apply ops via existing session apply proxy.
4. Run headed/headless Playwright; fix issues; commit; PR; merge.

## Acceptance Criteria

- [ ] Playwright smoke: load score, select range, transpose apply, undo
- [ ] Mobile viewport: library drawer, bottom chat, expand/back
- [ ] Version picker: label current state, hop to labeled version
- [ ] Pitch keypad adds a note via click apply
- [ ] Inspector can set tempo / dynamic / lyrics on selection or caret measure
- [ ] CI green; PR merged to main
- [ ] Deploy when Railway token present (tracked separately)

## Risks / Open Questions

- Soft decision: Playwright runs against `npm start` + `npm run agent` (or start-prod) in CI with stubbed LLM if needed — click apply does not need XAI key.
- Soft decision: version picker is linear list of labeled + recent mutations (not full branch graph).
- Deploy remains blocked without Railway login/token in this agent environment.
