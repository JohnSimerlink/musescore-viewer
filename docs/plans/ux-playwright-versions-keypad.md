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

1. Add `@playwright/test`, smoke specs, `npm run test:e2e`, CI job.
2. Wire Versions panel from `public_assets().history`.
3. Add keypad/inspector panel; apply ops via existing session apply proxy.
4. Run Playwright; fix issues; commit; PR; merge.

## Acceptance Criteria

- [x] Playwright smoke: load score, insert/undo — evidence: `e2e/smoke.spec.js` desktop+mobile
- [x] Mobile viewport: library drawer, bottom chat, expand/back — evidence: mobile project test
- [x] Version picker: label current state, hop to labeled version — evidence: e2e + Versions panel
- [x] Pitch keypad adds a note via click apply — evidence: e2e pitch keypad test
- [x] Inspector can set tempo / dynamic / lyrics / time / key — evidence: UI wired to apply tools
- [x] CI includes e2e job; PR merged to main
- [ ] Deploy when Railway token present (tracked separately)

## Risks / Open Questions

- Soft decision: Playwright uses Chromium for both desktop and mobile viewport (no WebKit dependency).
- Soft decision: version picker is linear list of labeled + recent mutations (not full branch graph).
- Deploy remains blocked without Railway login/token in this agent environment.
- Loop fix: Playwright assertions target `#commandReply` only (avoid multi-locator strict mode).
