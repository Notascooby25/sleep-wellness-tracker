# Dependency alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (native). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close or correctly dismiss the 28 open Dependabot alerts on `frontend-web/package-lock.json` (7 high, 16 medium, 5 low), and stop the lock file and the production build disagreeing.

**Architecture:** Update packages within their existing version ranges first (no major upgrades), commit a refreshed lock file, make the Docker and CI builds install exactly what the lock says (`npm ci`), then re-check which alerts remain. Anything that needs a major upgrade (SvelteKit 3, Vite 8) is listed for the owner to decide, not done.

**Tech Stack:** npm, SvelteKit 2 (adapter-node), Svelte 5, Vite 5. No new packages.

**Spec:** Findings from the 2026-11-17 re-audit (conversation) and the Dependabot alert list.

## Findings that shape the plan

- **Lock and build disagree.** `frontend-web/Dockerfile` copies only `package.json` and runs `npm install`, and CI also runs `npm install`. So production images resolve the newest versions within the ranges at build time, and ignore `package-lock.json`. The lock (what Dependabot scans) is stale: SvelteKit 2.58.0, devalue 5.7.1, svelte 5.55.5, postcss 8.5.12. Production is probably already on newer versions than the lock, but nobody has checked.
- **Runtime exposure is smaller than the alert count.** The production image holds only `/app/build` (no `node_modules`), so these packages ship bundled into the server code, not as separate installs. The app uses none of: remote functions (`$app/server`), prerendering, `use:enhance`, `{@html}` or `hydratable`, which is where most of the SvelteKit and Svelte advisories are.
- **Dev-only alerts:** esbuild, vite and its `launch-editor` helper only matter on the dev server, which isn't in production.
- **Some fixes only exist in a new major version.** One high SvelteKit alert (form-data DoS in remote functions) is fixed only in 3.1.1; the 2.x line has no fix. The app doesn't use remote functions, so it can likely be dismissed with that reason, but that is the owner's call.

## Global Constraints

- No major version upgrades in this PR. No new dependencies.
- `npm audit` and `npm outdated` send the package list to the public npm registry, so each needs the owner's OK first (asked below).
- Changing the Dockerfile and CI install step is a build-process change: the owner approves it (asked below).
- Public repo: alert details beyond severity and package names stay in chat and the saved report, not in the PR text.
- Release: version 4.21.10 with a plain-English changelog entry.

## Review Focus

- A dependency update that quietly changes the build output (CSS, routes): `svelte-check` and the build must pass and the preview must load every page.
- `npm ci` failing because the lock and `package.json` ranges disagree (it is strict): the lock must be regenerated from `package.json` so they agree.
- The CI build cache (`type=gha`) keeping old layers: confirm the image actually contains the lock's versions.
- The update bar and service worker still behave after the update (the version signal changes per build).

---

### Task 1: See what production actually has (needs owner OK)

- [ ] **Step 1 (needs OK to contact the npm registry):** In a temp copy of `frontend-web`, run `npm install --package-lock-only` (fresh resolve from `package.json` only, the same as production builds) and read the resolved versions of `@sveltejs/kit`, `svelte`, `devalue`, `postcss`, `vite`, `esbuild`, `cookie`, `nanoid`, `source-map-js`. Compare each with the Dependabot "first patched version" table.
- [ ] **Step 2:** Write the comparison to the saved report outside the repo ("production likely patched / still vulnerable / needs a major upgrade") per alert.

### Task 2: Refresh the lock file within ranges

**Files:** Modify: `frontend-web/package-lock.json` (and `package.json` only if a range must be raised within the same major).

- [ ] **Step 1:** Run `npm update` in `frontend-web` and commit the regenerated lock (also fixes its stale `4.20.0` version field).
- [ ] **Step 2:** Run `npm run check` and `npm run build`; expect 0 errors, build succeeds.
- [ ] **Step 3:** Commit `chore(web): refresh lock file within existing version ranges`.

### Task 3: Make builds use the lock (needs owner OK)

**Files:** Modify: `frontend-web/Dockerfile` (copy `package.json` and `package-lock.json`, run `npm ci`), `.github/workflows/build-amd64.yml` (the "Install frontend deps" step: `npm ci`).

- [ ] **Step 1:** Make the two edits. This touches `.github/`, so the PR description says so in plain English, because a pull request can weaken its own checks. The edit only tightens the install step.
- [ ] **Step 2:** Build the Docker image locally through the preview (`scripts/preview.sh up`) and check the app loads; check the bundled version of `devalue` and `kit` in the image match the lock.
- [ ] **Step 3:** Commit.

### Task 4: Re-check and report

- [ ] **Step 1:** Push; wait for Dependabot to re-scan; list the alerts that remain, grouped: (a) fixed by the refresh, (b) need a major upgrade, (c) not reachable in this app (dev-only or unused feature), with a recommended dismiss reason each, for the owner to apply.
- [ ] **Step 2:** `differential-review`, `pwa-failure-points` quick check, changelog and version 4.21.10, open the PR, wait for the owner's go-ahead.
- [ ] **Step 3 (after go-live):** open the app, check the update bar and every page.

**Honest limits:** I can't tell which exact versions production runs today without Task 1, and I can't judge reachability of every advisory beyond what the app's code shows. Major upgrades (SvelteKit 3, Vite 8) are out of scope and would be their own plan.
