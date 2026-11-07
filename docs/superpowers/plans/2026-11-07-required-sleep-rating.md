# Required Last Night's Sleep Rating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require a Last Night's Sleep rating (1 to 5) before saving an entry whenever the Morning / Waking Feedback category or any of its activities are selected, preventing accidental saves without a rating while keeping the UI clear and gentle.

**Architecture:** Client-side validation in `frontend-web/src/routes/mood-entry/+page.svelte`. When morning feedback is active, dynamically update the sleep rating label from "(optional)" to "(required)", display an inline helper notice above the Save button when a rating is missing, and block form submission with an error status plus auto-scroll to the sleep rating pills if Save is clicked without a rating.

**Tech Stack:** Svelte 5, SvelteKit, TypeScript, CSS semantic tokens.

**Spec:** Chat agreement in session `ad7bbe24-ea7e-4c2e-bd5d-8e479b656658` (small change).

## Global Constraints
- Follow "The Quiet Sanctuary" design language from `DESIGN.md`.
- No new packages or dependencies.
- No database or backend changes needed (`subjective_sleep_rating` is already supported).
- Must pass `npm run check` and `npm run build` in `frontend-web`.

## Review Focus
- **Input without Morning Feedback:** Selecting activities from other categories must not require a sleep rating.
- **Rating toggle / unselect:** Tapping an already selected rating pill deselects it to `null`; the validation must reactively mark it missing again.
- **Auto-scroll on mobile:** Clicking "Save Entry" without a rating smoothly scrolls the page to the sleep rating container so the user does not need to scroll manually.
- **Form reset:** After successful save, the form reset clears the rating and any validation notices.
- **No race or freeze:** Saving must not get stuck in a `busy = true` state when validation blocks.

---

### Task 1: Add required sleep rating validation, dynamic labels, inline notice, and auto-scroll

**Files:**
- Modify: `frontend-web/src/routes/mood-entry/+page.svelte:363-425,485-502,550-560,654-709`

**Interfaces:**
- Consumes: `sleepRatingVisible: boolean`, `subjectiveSleepRating: number | null`, `selected: Set<number>`, `categories: Category[]`, `activities: Activity[]`
- Produces: `sleepRatingMissing: boolean`, blocked `submitEntry` when missing, inline notice and auto-scroll

- [ ] **Step 1: Check existing build and type checks**
Run: `npm run check --prefix frontend-web && npm run build --prefix frontend-web`
Expected: PASS with 0 errors.

- [ ] **Step 2: Implement reactive state and submission guard in `frontend-web/src/routes/mood-entry/+page.svelte`**
1. Add reactive boolean:
   ```ts
   $: sleepRatingMissing = sleepRatingVisible && subjectiveSleepRating === null;
   ```
2. In `submitEntry`:
   Add validation guard before submitting:
   ```ts
   if (sleepRatingVisible && subjectiveSleepRating === null) {
     status = 'Please choose a sleep rating (1 = great, 5 = poor) to save your morning entry.';
     if (typeof document !== 'undefined') {
       const el = document.getElementById('sleep-rating-section');
       el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
     }
     return;
   }
   ```
   Ensure `busy` remains `false`.

- [ ] **Step 3: Update template markup and styling in `frontend-web/src/routes/mood-entry/+page.svelte`**
1. Add `id="sleep-rating-section"` to the sleep rating block.
2. Update the header label to display `(required; 1 = great, 5 = poor)` with subtle emphasis when `sleepRatingMissing` is true.
3. Above the Save Entry button, display an inline notice when `sleepRatingMissing`:
   ```svelte
   {#if sleepRatingMissing}
     <p class="sleep-required-notice">
       Please select a rating for <strong>Last Night's Sleep</strong> above before saving.
     </p>
   {/if}
   ```
4. Add CSS for `.sleep-required-notice` adhering to the Quiet Sanctuary palette:
   Soft amber warning background (`#fff8e6`), warm amber border (`#f6d892`), dark amber text (`#7a4f01`), rounded corners (`10px`), padding (`0.45rem 0.75rem`), font size (`0.84rem`).

- [ ] **Step 4: Run type-check and build to verify changes**
Run: `npm run check --prefix frontend-web && npm run build --prefix frontend-web`
Expected: PASS with 0 errors.

- [ ] **Step 5: Commit changes to a working branch**
Run:
```bash
git checkout -b feat/required-sleep-rating-morning
git add frontend-web/src/routes/mood-entry/+page.svelte
git commit -m "feat(mood-entry): require sleep rating when morning feedback is selected"
```

---

### Task 2: Verification, preview test, and safe-change handover

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run full engineering checks and CI suite**
Run:
- `npm run check --prefix frontend-web`
- `npm run build --prefix frontend-web`
- `ruff check --select E4,E7,E9,F backend/app`
- `bash scripts/tests/test_preview.sh`

- [ ] **Step 2: Update `CHANGELOG.md`**
Add an entry under unreleased/new version documenting the required sleep rating reminder for Morning / Waking Feedback.

- [ ] **Step 3: Verify preview environment**
Run `scripts/preview.sh up` (or verify via preview check) and test:
1. Select an activity under Morning / Waking Feedback -> verify "(required)" label and reminder text appear.
2. Tap "Save Entry" without rating -> verify save is blocked, warning shows, and view scrolls to rating pills.
3. Tap rating pill 1-5 -> verify reminder clears and save succeeds.
4. Select activity from another category -> verify sleep rating is not shown or required and save works normally.
