# "New version available" banner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** When a new release is deployed, anyone with the app open sees a banner under the header; clicking it clears old caches and loads the new version.

**Architecture:** Use SvelteKit's built-in version detection (`kit.version.pollInterval` + the `updated` store from `$app/stores`), plus an extra check when the tab/PWA becomes visible again. A small module `appUpdate.ts` does the refresh (ask service worker to update, delete CacheStorage entries, full reload). A banner component shows in the layout. Never reloads by itself, so unsaved form input is never lost.

**Tech Stack:** SvelteKit 2.58 (Svelte 5, legacy `on:` syntax as used in the layout), adapter-node, existing `static/sw.js`. No new dependencies.

**Spec:** Agreed in conversation 2026-11-17 (design approved: SvelteKit detection, slim banner, click-to-update, never automatic, separate branch `update-banner`).

## Global Constraints

- No new dependency, no data/API/schema change.
- Design tokens/look: flat, pale blue `#dceeff` fill, `#173a5c` text, `#9ec0e7` border, 10px radius, DM Sans/inherited font. No shadows.
- Banner is `role="status"`, button is a real `<button>`, 44px tall on touch screens.
- Do not show on `/login`.
- Never auto-reload. Never cache API responses (service worker rule unchanged).
- Public repo: no hostnames/IPs in code or docs.
- Release: version 4.21.5 (4.21.3 is live; 4.21.4 is reserved by the open DM Sans PR #39; if #39 merges first, use the next free number) with a plain-English CHANGELOG entry.

## Review Focus

- Mood Entry half filled in when an update lands: nothing happens until the user clicks.
- Backend/Docker restarting mid-deploy so the version check fails: no error shown, banner not shown, check retried later.
- Offline: the check fails silently; clicking the banner while offline must not wipe the caches (offline page) and leave a broken reload, so cache clearing only happens if the reload target is reachable.
- Phone PWA resumed after hours in the background: re-check on `visibilitychange`.
- User clicks twice: second click is ignored while refreshing.

---

### Task 1: Refresh helper

**Files:**
- Create: `frontend-web/src/lib/appUpdate.ts`

**Interfaces:**
- Produces: `export async function refreshToLatest(): Promise<void>` — in order: (1) `fetch('/_app/version.json', { cache: 'no-store' })`; if it throws or `!ok`, return without touching anything (offline guard); (2) `navigator.serviceWorker.getRegistration()` then `registration?.update()` inside try/catch; (3) delete every key from `caches.keys()` (guarded by `'caches' in window`, try/catch); (4) `location.reload()`.

- [ ] **Step 1:** Implement `refreshToLatest` as above in `appUpdate.ts`; each step in its own try/catch so one failing step never blocks the reload.
- [ ] **Step 2:** Run `cd frontend-web && npm run check` — expect 0 errors (the 1 existing login autofocus warning is fine).
- [ ] **Step 3:** Commit `feat(web): refreshToLatest helper for app updates`.

### Task 2: Turn on detection and add the banner

**Files:**
- Modify: `frontend-web/svelte.config.js` (add `version: { pollInterval: 300000 }` inside `kit`)
- Create: `frontend-web/src/lib/UpdateBanner.svelte`
- Modify: `frontend-web/src/routes/+layout.svelte` (import and render `<UpdateBanner />` directly after the `<header>` inside the non-login branch)

**Interfaces:**
- Consumes: `refreshToLatest()` from Task 1; `updated` from `$app/stores`.
- Produces: `UpdateBanner.svelte`, no props. Renders only when `$updated` is true. Text: "A new version of the app is available." with a button "Update now". While refreshing, button is disabled and reads "Updating…". `onMount`: add a `visibilitychange` listener that calls `updated.check()` when `document.visibilityState === 'visible'`; remove it on destroy. Styles use the tokens listed in Global Constraints; `@media (pointer: coarse)` gives the button `min-height: 44px`.

- [ ] **Step 1:** Add the `version.pollInterval` option and the component.
- [ ] **Step 2:** Mount it in the layout (not rendered on `/login`, which already uses the other branch).
- [ ] **Step 3:** Run `npm run check` and `npm run build`; expect 0 errors and a successful build, and `build/client/_app/version.json` exists.
- [ ] **Step 4:** Commit `feat(web): update banner with click-to-refresh`.

### Task 3: Release notes and docs

**Files:**
- Modify: `CHANGELOG.md` (new top entry), `frontend-web/package.json` (version)
- Modify: `frontend-web/static/sw.js` comment only if wrong: the `CACHE_NAME` bump comment (no behaviour change; leave the name alone).

- [ ] **Step 1:** Add changelog entry in plain English ("A bar now appears at the top when a new version has been released; tap Update now to load it. It never reloads on its own, so nothing you're typing is lost.") and bump the version.
- [ ] **Step 2:** Commit `docs: changelog and version for update banner`.

### Task 4: Prove it works (preview, no browser tooling)

- [ ] **Step 1:** `scripts/preview.sh up`; record `curl -s localhost:18510/_app/version.json` (must return a JSON `version`).
- [ ] **Step 2:** Add a trivial whitespace-only commit, `scripts/preview.sh up` again; `version.json` must now return a different value. This proves the signal the banner relies on changes per build.
- [ ] **Step 3:** Hand the owner the try-out list: open the preview in a tab, redeploy as in Step 2, within 5 minutes (or on switching tabs) the bar appears; click it; page reloads on the new build; start typing on Mood Entry before the update to confirm nothing reloads on its own; check phone later.
- [ ] **Step 4:** Run `differential-review` and the `pwa-failure-points` quick check, open the PR with its change record, then wait for the owner's go-ahead.

**Honest limits:** there is no front-end test framework (adding one is a new dependency, so I'm not doing that without asking). The banner appearing and the click-through can only be seen in a real browser by the owner; I can prove the version signal changes but not the on-screen result.
