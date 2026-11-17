# Error and loading states Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native). Steps use checkbox (`- [ ]`) syntax.

**Goal:** When something goes wrong (offline, slow, signed out, bad input, server error) every page tells the person what happened and what to do in plain words, never a raw technical string, and long actions can't be triggered twice.

**Architecture:** One shared helper turns any failure into a friendly sentence; `api.ts` throws a typed error carrying the HTTP status; a signed-out response sends the person to the login page and brings them back; pages use the helper instead of printing the raw error; error text is announced to screen readers; loading and double-submit gaps found in the review are closed.

**Tech Stack:** SvelteKit 2 / Svelte 5. The helper is plain JavaScript with type comments so it can be tested with Node's built-in test runner, with no new dependency.

**Spec:** Re-audit findings, 2026-11-17, plus the recon below.

## What the review found (the evidence this plan rests on)

- **Raw technical text reaches the screen in 47 places.** Pages build messages like `` `Add failed: ${error}` ``, so people see things like `Error: 422 {"detail":[…]}`, `TypeError: Failed to fetch` (the same text you saw on the login page) or `AbortError: signal is aborted without reason` (what a 12-second timeout looks like).
- **No signed-out handling.** `api.ts` throws `401 …` and each page just prints it. A session that expires mid-use never sends you to the login page.
- **Loading and double-submit gaps.** Analytics has no loading state and no disabled buttons. Manage Activities and Manage Categories have no busy state on save and delete. Several other pages disable buttons but not consistently.
- **Errors aren't announced.** Only 5 `role="status"`/`aria-live` regions exist across 13 pages, so a screen reader user never hears "Save failed".
- **Good already:** `api.ts` times out after 12 seconds, de-duplicates in-flight GETs and invalidates caches on writes; destructive actions ask `confirm()` first; the Dashboard, Mood Log and Export pages have real loading states.

## Global Constraints

- No new dependency and no `.github/` change in this PR (a CI step for the new test is offered separately, see the end).
- Keep existing message prefixes ("Save failed", "Load failed") and only replace the technical tail, so pages still read the same.
- Messages are short, name what happened, and say what to do ("Check your connection and try again").
- Never show server response bodies to the person; keep them in the browser console for debugging.
- Don't change the 12 s timeout, the cache rules or any backend behaviour.
- Version 4.21.12, plain-English changelog.

## Review Focus

- A wrong password on the login page must still say "Incorrect password." and must not trigger the signed-out redirect (login uses its own `fetch`, not `api()`).
- Two requests failing with 401 at once must cause one redirect, not two.
- The redirect target after re-login keeps the path and query string (`?redirect=` already supported by the login page) and is only ever the app's own path.
- An aborted request (timeout, page navigation) must read "That took too long" for a timeout and be silent when the person just navigated away.
- Offline (`navigator.onLine` false or `TypeError: Failed to fetch`) says "You appear to be offline".
- A 422 validation response with a readable `detail` shows that detail in plain words; unreadable bodies fall back to a generic line.

---

### Task 1: Friendly errors helper, with tests

**Files:**
- Create: `frontend-web/src/lib/errors.js` (+ `errors.d.ts` for types), `frontend-web/src/lib/errors.test.js`
- Modify: `frontend-web/src/lib/api.ts`

**Interfaces:**
- Produces: `export class ApiError extends Error { status: number; detail: unknown }`; `export function describeError(error: unknown): string`, returning plain-English text for: offline/`Failed to fetch`, timeout/`AbortError`, 401 ("You've been signed out"), 403, 404, 408/429, 422 (readable `detail`, else "Some of that wasn't accepted"), 5xx ("Something went wrong on the server"), anything else ("Something went wrong").

- [ ] **Step 1:** Write `errors.test.js` first using `node --test`; one test per case in the list above, with the exact expected sentences; run `node --test frontend-web/src/lib/errors.test.js` and watch it fail.
- [ ] **Step 2:** Implement `errors.js`; run the tests until they pass.
- [ ] **Step 3:** In `api.ts`, throw `ApiError(status, detail)` instead of `Error('401 …')` (message stays human-readable-safe); log the raw body with `console.warn`; keep everything else identical.
- [ ] **Step 4:** `npm run check`, `npm run build`, tests pass. Commit.

### Task 2: Signed-out handling

**Files:** Modify `frontend-web/src/lib/api.ts` (or a small `session.ts` imported by it).

- [ ] **Step 1:** On a 401 from `api()`, once per page load, `goto('/login?redirect=' + encodeURIComponent(path + search))` and then throw the `ApiError` quietly (pages' catch blocks will show "You've been signed out. Please sign in again." only if still visible). Guard with a module-level flag so concurrent 401s redirect once. Skip for paths under `/auth/`.
- [ ] **Step 2:** Add to `errors.test.js` a test that the redirect target helper only returns an app-internal path (starts with `/`, not `//`).
- [ ] **Step 3:** Commit.

### Task 3: Use the helper on every page

**Files:** the 11 pages that print `${error}` (manage-categories, manage-activities, mood-entry, mood-log, garmin-log, garmin-lifestyle-impact, acupuncture-report, analytics, dashboard, settings and its two sub-pages).

- [ ] **Step 1:** Replace each of the 47 raw interpolations (`${error}`, `${e}`, `String(error)`, `error.message`) with `${describeError(error)}`, keeping the prefix; add `import { describeError } from '$lib/errors'`. Mechanical; diff review: every changed line differs only in that expression plus the import.
- [ ] **Step 2:** Make `status`/error paragraphs live regions: `role="status"` for progress and success text, `role="alert"` for failures (about 15 render sites).
- [ ] **Step 3:** `npm run check` and build. Commit.

### Task 4: Close loading and double-submit gaps

**Files:** `analytics/+page.svelte`, `manage-activities/+page.svelte`, `manage-categories/+page.svelte`, plus any page where the sweep finds a save/delete button without a busy guard.

- [ ] **Step 1:** Analytics: add an `isLoading` flag around its loads with a "Loading analytics…" line and a "Try again" button on failure.
- [ ] **Step 2:** Manage Activities and Manage Categories: a `busy` flag set during add, save and delete; buttons `disabled={busy}`; label changes to "Saving…".
- [ ] **Step 3:** Sweep every page for async click handlers that call `postJson`/`putJson`/`deleteJson` without a guard and add the same pattern; list each one in the PR.
- [ ] **Step 4:** `npm run check` and build. Commit.

### Task 5: Prove and release

- [ ] **Step 1:** Run the tests; build; `scripts/preview.sh up`; `curl` every page for 200.
- [ ] **Step 2:** Try failure paths on the preview with `curl`: wrong login still returns the right status; stop the backend container briefly and confirm the proxy returns 502 and a page shows the friendly "offline/server" wording (owner confirms in the browser).
- [ ] **Step 3:** Changelog and version 4.21.12; `differential-review`; `pwa-failure-points` quick check (sign-in and error handling areas are touched); open the PR; wait for the owner.

**Honest limits:** I can test the message-mapping and the redirect rule with real automated tests, but how the pages look when an error appears, and the signed-out redirect in a browser, only you can see. Deliberately not changing: backend error shapes, the 12 s timeout, offline queueing of writes (a larger feature).

**Offered separately (needs your OK):** a one-line CI step to run `node --test` on every pull request so the helper's tests keep running. That edits `.github/`, so it would be its own tiny PR.
