# Colour tokens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the front end use the design tokens in `frontend-web/src/tokens.css` instead of about 146 distinct hard-coded hex colours, in two separate PRs.

**Architecture:** PR A swaps only hex values that already equal a token (provably no visual change) and adds tokens for colours repeated 4+ times. PR B snaps the remaining near-duplicate blues to the nearest token (small visible shifts, owner reviews in preview). A throwaway script (kept in the scratchpad, never committed) does the replacing and proves PR A by reversal.

**Tech Stack:** SvelteKit 2 / Svelte 5 CSS (`<style>` blocks, `app.css`, inline `style=""`), plain CSS custom properties. No new dependency.

**Spec:** Approved in conversation 2026-11-17 (approach 2: exact matches first, then consolidate the blues, as two PRs). Reference: `DESIGN.md` ("Quiet Sanctuary").

## Global Constraints

- Scope is CSS only: `<style>` blocks, `app.css`, inline `style="…"` attributes. JavaScript string colours (mood-scale objects, canvas `fillStyle`, chart palettes in `<script>`) are left alone and listed as out of scope, because `var()` does not work in them.
- Chart/data colours (`#ef4444`, `#f59e0b`, `#84cc16`, `#10b981`, `#22c55e`, `#7c3aed`) become their own named tokens (`--color-data-*`), never merged into the blues.
- Keep DESIGN.md rules: flat surfaces (no new shadows), no `#000`, no pure-white page background (white cards stay).
- No new dependency, no layout or copy change. Public repo: no hostnames or secrets.
- One version and changelog entry per PR: PR A = next free version after 4.21.7 (4.21.8), PR B = 4.21.9 (re-check `main` before each).
- Update `DESIGN.md` color list when tokens are added (docs travel with the change).

## Review Focus

- A hex inside a CSS comment, URL or `content:` string being rewritten by mistake: replacement only inside declaration values.
- Uppercase vs lowercase and 3-digit (`#fff`) vs 6-digit forms of the same colour: all compared normalised to lowercase 6-digit.
- A colour used as `rgba()` with the same RGB as a token: left as is (not a hex), noted for PR B.
- `app.css` `:root` gradient and `body` colours moving to `var()` must keep the same computed values (the page background).
- A token used before `tokens.css` loads (the `@import` order in `app.css`): tokens must be defined on `:root` and `app.css` already imports them first.

---

### Task 1: Inventory and mapping table (no repo change)

**Files:** scratchpad only: `colour_inventory.py` (not committed).

**Interfaces:**
- Produces: a table `hex -> count -> files` and the list of hex values that exactly equal an existing token, plus those repeated 4+ times that have no token, saved in the scratchpad for Tasks 2 and 3.

- [ ] **Step 1:** Write a script that scans `frontend-web/src/**/*.svelte` and `app.css`, extracts hex colours only from CSS contexts (`<style>` blocks, `style="…"` attributes, `app.css`), normalises to lowercase 6-digit, and counts per value. Excludes `<script>` blocks.
- [ ] **Step 2:** Run it; expected: ~146 distinct values, matches the earlier count within a few (script-context values excluded). Save output.

### Task 2: PR A, exact matches to existing tokens

**Files:**
- Modify: every `.svelte` and `app.css` file containing a matching hex; `frontend-web/src/tokens.css` (new tokens); `DESIGN.md`; `CHANGELOG.md`; `frontend-web/package.json`.

**Interfaces:**
- Consumes: Task 1 table.
- Produces: `tokens.css` with the existing 13 tokens plus new ones for repeated colours with no token yet, named by role (e.g. `--color-border-soft`, `--color-text-link`, `--color-data-red`); every CSS hex equal to a token replaced by `var(--token)`.

- [ ] **Step 1:** Add the new tokens (colours repeated 4+ times with no token, using their exact current values, so nothing changes) to `tokens.css`.
- [ ] **Step 2:** Write the replacement script: for every CSS-context hex whose normalised value equals a token's value, replace with `var(--token)`. Write each file to a temp file then rename (clean tree, files are in git).
- [ ] **Step 3 (proof):** Run the reverse script (substitute every `var(--color-…)` back to its hex from `tokens.css`) over the changed files and compare with the pre-change files via `git diff --no-index` or `git stash` copies. Expected: byte-identical except letter case and 3-vs-6-digit hex forms; list any other difference and fix.
- [ ] **Step 4:** `npm run check` and `npm run build`; expected 0 errors, build succeeds. Compare the built CSS: count distinct hex values dropped; page background in `app.css` unchanged.
- [ ] **Step 5:** Update `DESIGN.md` colour list, CHANGELOG entry ("Behind-the-scenes tidy-up; the app looks identical"), version bump; commit; push; run the preview; open PR A.

### Task 3: PR B, consolidate near-duplicate blues (starts after PR A is merged)

**Files:** same set as Task 2, plus `tokens.css`, `DESIGN.md`, changelog, version.

**Interfaces:**
- Consumes: Task 2's tokens, merged to `main`.
- Produces: the remaining hard-coded blues/greys replaced with the nearest token (nearest in Lab colour, only if the difference is small, with a cap), and a printed list of anything above the cap left for the owner to decide.

- [ ] **Step 1:** Script computes, for each remaining non-token hex, the nearest token and the colour distance; replaces if under the cap (cap chosen so shifts are barely visible, e.g. ΔE under about 6), otherwise lists it.
- [ ] **Step 2:** Confirm text colours keep contrast ≥ 4.5:1 on their backgrounds after snapping (script checks the pairs it can see; list any it can't).
- [ ] **Step 3:** `npm run check`, build, preview; hand the owner a try-out list of the screens with the most changed colours (Analytics, Mood Entry, Dashboard, Settings) on PC and phone.
- [ ] **Step 4:** CHANGELOG ("Colours made consistent; small shade differences possible"), version bump, PR B, wait for the owner.

**Honest limits:** I cannot view your pages (health data), so PR B's visual result is judged by you in the preview; PR A is checked by the reversal proof and the build. There is no front-end test framework.
