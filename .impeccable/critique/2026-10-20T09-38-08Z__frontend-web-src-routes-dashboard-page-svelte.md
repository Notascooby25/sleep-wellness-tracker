---
target: frontend-web/src/routes/dashboard/+page.svelte
total_score: 17
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
target_identity: "file:/home/andyl/sleep-wellness-tracker/frontend-web/src/routes/dashboard/+page.svelte"
target_fingerprint: "sha256:85310a463abae9b406c5131e0ed6364f93f4e0efc9feb81a45cde1fad5656d2e"
target_path: /home/andyl/sleep-wellness-tracker/frontend-web/src/routes/dashboard/+page.svelte
timestamp: 2026-10-20T09-38-08Z
slug: frontend-web-src-routes-dashboard-page-svelte
closed: true
---
Method: dual-agent (A: 1822a988-0ab6-47f0-9e77-cfbd33035431 · B: 983dd838-257f-4a48-89ac-9db6748d2ab4)

# Impeccable Design Critique: Sleep & Wellness Tracker Dashboard

**Target:** `frontend-web/src/routes/dashboard/+page.svelte` (with `+layout.svelte`, `tokens.css`, `app.css`)  
**Creative North Star:** "The Quiet Sanctuary" (`DESIGN.md`, `PRODUCT.md`)

---

### Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|:-----:|-----------|
| 1 | Visibility of System Status | 1 | No skeleton loader during 5 concurrent API calls; layout jumps abruptly (CLS); no timestamp indicating when Garmin data was last synced; silent failure if data missing. |
| 2 | Match System / Real World | 2 | Readiness is an opaque 40/30/30 formula with no user explanation; naked biometric values (e.g. "HRV 48ms") lack personal baseline boundaries or contextual framing. |
| 3 | User Control and Freedom | 2 | No manual "Sync Now" / "Refresh" trigger; no way to retry failed queries or dismiss/acknowledge advice cards. |
| 4 | Consistency and Standards | 2 | CTA button `.btn-primary` uses un-tokenized cobalt `#3c79c5` and `border-radius: 999px` (violating `DESIGN.md`'s `#dceeff` and `10px`); `.hero` card uses an unapproved drop shadow violating the Flat Sanctuary Rule. |
| 5 | Error Prevention | 2 | API or auth errors cause biometric sections to silently disappear rather than informing the user what happened or offering remediation. |
| 6 | Recognition Rather Than Recall | 2 | Snapshot pills show isolated metrics with no comparison against user baselines, forcing recall of historical averages. |
| 7 | Flexibility and Efficiency | 2 | Static single-day view with no date traversal, no keyboard shortcuts (e.g. `M` for Mood Entry), and non-interactive pills that don't link to log details. |
| 8 | Aesthetic and Minimalist Design | 2 | Overwhelming 4.5rem score box dwarfs other content; hero repeats redundant label text; topbar packs 10 unchunked pills. |
| 9 | Error Recovery | 1 | Generic error copy ("Unable to load advice right now") with no explanation, troubleshooting guidance, or retry action. |
| 10 | Help and Documentation | 1 | Zero inline guidance, tooltips, or microcopy explaining readiness calculations, HRV baselines, or predictive advice factors. |
| **Total** | | **17/40** | **Poor (Major UX overhaul required)** |

---

### Design Specificity Verdict

**LLM Assessment (Unanchored):**
The design system defined in `DESIGN.md` describes **"The Quiet Sanctuary"**—a soft, low-contrast, reflective haven designed to turn wellness and sleep tracking into a peaceful ritual rather than an anxiety-inducing data chore. However, the current dashboard implementation largely feels like an administrative analytics widget:
1. **Cortisol-Inducing Alert Colors:** Instead of the tranquil morning sky palette, the readiness card applies high-saturation "traffic-light" alert boxes: high readiness in emerald (`#086c3a` on `#dcfae6`), mid readiness in amber (`#854d0e` on `#fef3c7`), and low readiness in alarming emergency red (`#b42318` on `#fee4e2`). If a user wakes up feeling depleted, greeting them with a glaring crimson score card reading "34%" with a 2px red border induces immediate morning cortisol spikes and health anxiety (orthosomnia).
2. **Abrupt Motion & CLS:** Five uncoordinated API calls trigger on mount without skeleton states, causing cards to violently pop into place once data resolves.
3. **Token Violations:** Legacy drop shadows linger on the `.hero` container (violating the "Flat Sanctuary Rule"), and buttons deviate from the design system's established tokens.

**Deterministic Scan:**
- Command: `impeccable detect --json frontend-web/src/routes/dashboard/+page.svelte frontend-web/src/routes/+layout.svelte`
- Findings: `0 violations` (Exit code 0).
- Detector Analysis: The mechanical detector confirms no prohibited fallback fonts (Inter/Roboto overuse), uncontained viewports, raw `#000000` text, or unstyled native controls. The issues on this surface are conceptual, typographic hierarchy, and tonal harmony rather than crude CSS syntax violations.

**Visual Overlays:**
No live browser automation tool was available in this headless CLI environment; live browser DOM injection and visual overlay generation were skipped.

---

### Overall Impression
The core value proposition—correlating Garmin biometrics with subjective self-reflection—is high-value and clearly functional. But aesthetically and emotionally, the dashboard currently acts as an aggressive KPI report rather than an introspective sanctuary. The biggest opportunity is transforming the morning greeting from a punitive traffic-light grading card into a compassionate, supportive wellness companion.

---

### What's Working
1. **Holistic Biometric-Subjective Fusion:** Bringing Garmin sleep/HRV metrics together with qualitative mood tracking and predictive lifestyle advice provides a compelling, unified view that native Garmin Connect misses.
2. **Solid Responsive Grid Foundation:** The CSS layout structure (`.grid.two`, `.grid.three`, collapsing cleanly below 860px) provides an orderly multi-column scaffold across desktop and mobile screens.
3. **Quiet Sanctuary Color Foundations:** The base tokens in `tokens.css` (Soft Morning Blue `#dceeff`, Deep Night Slate `#132238`, Muted Slate `#496685`) provide a peaceful foundation when adhered to consistently.

---

### Priority Issues

#### [P0] Alarming "Traffic Light" Color Inversion & Anxiety-Inducing Scoring
- **Why it matters:** Greeting an exhausted user with a high-saturation crimson badge (`#b42318` on `#fee4e2`) and a giant 4.5rem grade induces acute morning health anxiety and directly violates "The Quiet Sanctuary" north star.
- **Fix:** Replace traffic-light alerts with sanctuary-aligned calm tonal palettes (soft morning blue, muted slate, gentle sage). Pair the score with compassionate qualitative guidance ("Gentle Pace Recommended", "Ready for Action") instead of a raw punitive grade.
- **Suggested command:** `/impeccable quieter`

#### [P1] Severe Cumulative Layout Shift (CLS) & Missing Loading / Sync States
- **Why it matters:** On page load, cards pop in abruptly across 5 unsynchronized API promises. If sync fails, biometrics silently vanish with zero explanation.
- **Fix:** Add a calm skeleton loading state for the readiness card and snapshot pills. Add a clear metadata label ("Synced at 7:15 AM" or "Syncing Garmin data...") and a manual refresh trigger.
- **Suggested command:** `/impeccable harden`

#### [P1] Black-Box Readiness Score Without Breakdown or Baselines
- **Why it matters:** Readiness is presented as an unexplained number. Snapshot metrics (HRV, Stress) lack reference ranges or baseline bands, leaving the user unable to understand what drove their score.
- **Fix:** Introduce an expandable "Score Breakdown" or inline component cards showing how Sleep (40%), HRV baseline comparison (30%), and Stress (30%) contributed to the day's readiness.
- **Suggested command:** `/impeccable clarify`

#### [P2] Design System Inconsistencies & Token Drifting
- **Why it matters:** The hero card has an unapproved drop shadow; `.btn-primary` uses an un-tokenized cobalt `#3c79c5` and `999px` radius instead of `#dceeff` and `10px` radius; `app.css` hardcodes hex codes rather than consuming `tokens.css`.
- **Fix:** Remove `.hero` box-shadow to adhere to the Flat Sanctuary Rule; normalize button styling and tokens to match `DESIGN.md`.
- **Suggested command:** `/impeccable polish`

---

### Persona Red Flags

- **Alex (Impatient Power User):** Layout jumps right as Alex is about to tap the CTA button. No keyboard navigation shortcut (e.g. hitting `M` to jump directly into Mood Entry). Snapshot pills are unclickable text; Alex cannot click "Sleep 7h 23m" to jump directly into the Garmin Sleep Log.
- **Jordan (Confused First-Timer):** When logging in before the first Garmin sync completes, the readiness card and morning snapshot completely vanish. The screen only shows "Daily Dashboard" and a prompt saying "Keep logging your activities to receive personalized predictive advice!" Jordan assumes the app is broken because there is zero onboarding empty state (e.g. "Waiting for your first Garmin sync...").
- **Sam (Accessibility-Dependent User):** The Readiness Score is marked up as `<div class="readiness-value">{readinessScore}<small>%</small></div>` with no semantic heading level or descriptive `aria-label` (reads as "seventy-eight percent" with no context). The topbar navigation links do not use `aria-current="page"`, and focus indicators on pill links lack adequate contrast.
- **Riley (Deliberate Stress Tester):** When the Garmin API returns 401 or 500, `loadError` becomes true, but the biometric section silently vanishes with only a generic note: "Unable to load advice right now." If baseline numbers are missing or equal, the HRV normalization uses `(HRV - 20) / 60`, which produces misleading numbers on edge-case athletic HRV values (e.g. HRV of 110ms clamped awkwardly at 100).
- **Casey (Distracted Mobile User):** The topbar's 10 pill buttons wrap across 3 dense lines on a mobile viewport, pushing the hero and content halfway down the screen. The massive 4.5rem readiness score pushes the primary CTA button ("Log Today's Mood & Activities") completely below the fold.

---

### Minor Observations
- The hero card includes redundant subtitle copy ("Daily Dashboard - Your morning readiness and personalized advice") that takes up vertical space without delivering new information.
- The 10 items in the top navigation bar combine global navigation, progressive web app installation ("Install"), and session control ("Logout") into visually identical pills.
- The primary action button sits at the very bottom of the page, below all metric cards, requiring excessive scrolling on smaller mobile viewports.

---

### Questions to Consider
- What if the sanctuary led with qualitative emotional status and a supportive greeting rather than a raw percentage score?
- Could the interface support diurnal ambient theming—soft dawn hues in the morning shifting to warm twilight slates in the evening?
- Could the primary action adapt to the time of day: morning readiness reflection upon wake-up, mid-day check-in at lunch, and evening debrief before bed?
