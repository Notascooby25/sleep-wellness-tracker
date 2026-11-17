# Phone polish and loose ends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Finish the remaining items from the 2026-11-17 audit: easier tapping and readable text on a phone, a proper page-level heading on every page, stop the proxy sending an internal error string to the browser, and list what to do with the 14 open dependency alerts.

**Architecture:** Three small pull requests so each can be reviewed and reverted alone, in this order: (1) proxy tidy (invisible, no phone needed), (2) page headings (small visual risk), (3) touch targets and small text (needs a real phone). A fourth item is a read-only report.

**Tech Stack:** SvelteKit 2 / Svelte 5 CSS and markup, existing tokens in `frontend-web/src/tokens.css`. No new dependency, no `.github/` change.

**Spec:** Re-audit findings, 2026-11-17 (P2: touch targets, small text; P3: heading structure) and the proxy note from the differential review of PR #47.

## What the recon found

- **Small text:** 33 `font-size` values below 0.8rem. By file: Analytics 10, Mood Log 8, Garmin Log 6, Mood Entry 4, Dashboard 3, Settings 1, `app.css` 1. Values range from 0.64rem to 0.78rem (0.75rem is the most common, 12 uses).
- **Tap targets:** global `button` padding is `0.48rem 0.72rem` (about 33px tall). Smaller still: Mood Log `.btn-sm` (`0.3rem 0.55rem`), the chips (`.chip`, `.detail-chip` at 0.22rem, `.position-chip`, `.act-chip`), `.snap-pill`, `.mpill`, `.num-btn`, the Analytics heatmap toggle and `.btn-clear`/`.btn-subtle`. Only the menu, update bar and the Dashboard main buttons are 44px.
- **Headings:** the layout has the only `<h1>` (the site name, on every page). Each of the 13 pages titles itself with an `<h2>`, and 32 `<h3>`s sit below. No stylesheet targets `h2`, so pages use the browser's default `h2` size.
- **Proxy:** `routes/api/[...path]/+server.ts` line 157 returns `detail: String(error)` on a 502, e.g. `TypeError: fetch failed`, which can name the internal backend address.

## Global Constraints

- Desktop (mouse) look must not change. Touch rules live inside `@media (pointer: coarse)`; text-size changes are the one exception and are small (see Task 3).
- Keep DESIGN.md rules: tokens only for colours, flat surfaces, 10px/12px/16px radii.
- Body and secondary text floor: 0.8rem; DESIGN.md's label size stays 0.86rem.
- One version and one plain-English changelog entry per PR (4.21.13, 4.21.14, 4.21.15 in this order; re-check `main` before each).
- Phone-visible PRs wait for the owner's phone check before the go-ahead.

## Review Focus

- Chips and pills that wrap onto many more lines on a narrow phone once they are taller; check Mood Entry (most chips) and Mood Log.
- A 0.8rem floor making a tight table, the heatmap labels or the Garmin Log number buttons overflow sideways.
- The page-title `h1` keeping exactly today's size and spacing (it is replacing a browser-default `h2`), and the brand name in the header staying the same look.
- Screen-reader order: after the change each page has one `h1`, and sections below it still read in order.
- The 502 message the proxy returns still reads as "backend unavailable" to `describeError` (it keys off the 502 status, not the body).

---

### Task 1 (PR 1, version 4.21.13): Proxy stops leaking internal error text

**Files:** Modify `frontend-web/src/routes/api/[...path]/+server.ts` (catch block near line 157).

- [ ] **Step 1:** Replace `detail: String(error)` with a fixed `detail: 'The server could not be reached.'` and `console.error('API proxy failed', error)` so the real cause stays in the server log. The `message: 'Upstream backend unavailable'` stays (the mood-entry upload code still matches on it).
- [ ] **Step 2:** `npm run check`, `npm run build`, `node --test src/lib/*.test.js`; preview; stop the preview backend container briefly and confirm `curl` shows the 502 body without `TypeError`; restart it.
- [ ] **Step 3:** Changelog ("no visible change"), version, `differential-review`, PR with the `pwa-failure-points` result.

### Task 2 (PR 2, version 4.21.14): One `h1` per page

**Files:** the 13 `+page.svelte` files with `<h2>` page titles, `routes/+layout.svelte`, `app.css`.

- [ ] **Step 1:** In each page change the title `<h2>` to `<h1>`; in the layout change the header's `<h1>` to a non-heading element (`<p class="brand">`) with the same visual style.
- [ ] **Step 2:** In `app.css` add `main h1 { font-size: 1.5em; margin: 0.83em 0; }` (the exact browser-default `h2` values) so page titles look identical to now; check the preview for any page whose title sits inside a styled `.hero` that already sets its own size.
- [ ] **Step 3:** Keep the `h3` sections as they are (a skipped level is minor and changing 32 headings is out of scope); note it in the PR.
- [ ] **Step 4:** Verify with `curl` that each page has exactly one `<h1>`; check, build, preview, reviews, PR.

### Task 3 (PR 3, version 4.21.15): Touch targets and small text (phone check required)

**Files:** `app.css` plus the page files named in the recon.

- [ ] **Step 1:** In `app.css` add one block `@media (pointer: coarse)` giving `button`, `select`, text-type `input`, and the named chip/pill classes `min-height: 44px` with matching vertical padding and `display: inline-flex; align-items: center`; checkboxes and radios get a 44px label area, not a bigger box.
- [ ] **Step 2:** Raise every `font-size` below 0.8rem to 0.8rem in the six files listed (33 values). Exception: purely decorative micro-labels inside the Analytics heatmap stay as they are if raising them breaks the grid; list any such in the PR.
- [ ] **Step 3:** `npm run check`, build, preview; hand the owner a phone try-out list (Mood Entry chips and pills, Mood Log rows and buttons, Garmin Log number buttons, Analytics heatmap toggle, Settings) and wait. Fix anything that wraps badly on the same branch.
- [ ] **Step 4:** Changelog, version, `differential-review`, quick `pwa-failure-points` check (layout on phone), PR.

### Task 4 (no code): Dependency alerts report

- [ ] **Step 1:** List the 14 open Dependabot alerts (package, severity, why it likely doesn't apply or what upgrade fixes it) in chat and a saved report outside the repo.
- [ ] **Step 2:** Dismissing an alert changes GitHub's security state, so I will only propose reasons; you click Dismiss (or tell me explicitly to do it with the GitHub command line).

**Honest limits:** I can't see the pages (they hold health data) and there's no screenshot tooling, so touch targets and wrapping can only be proven by your phone. Task 3 is the only one with real visual risk; Tasks 1 and 4 are invisible, and Task 2 should be pixel-identical but only you can confirm.

**Not included:** dark mode (your decision), changing the 32 `h3`s, and offline queueing of writes (a larger feature).
