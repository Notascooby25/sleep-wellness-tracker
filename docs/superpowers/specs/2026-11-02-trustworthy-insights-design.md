# Trustworthy insights: Lifestyle Impact and headache triggers

Date: 2026-11-02
Status: draft, awaiting owner approval

## Why

The app logs evening habits, overnight events, morning feedback, symptoms and Garmin data so the owner can work out what affects their sleep and what sets off their headaches. The Lifestyle Impact page and the headache trigger section of the Acupuncture Report are meant to answer those questions. At the moment they give answers that contradict common sense and each other: an item that is known to harm sleep can be listed as helping it, items logged on the same days get identical scores, and results built on two or three days are presented as findings.

The owner wants results that are believable and useful: a short list of things that really seem to matter, with an honest sign of how sure the app is. A noisy list of "impacts" is worse than no list.

## What is wrong today

These are confirmed by reading the code unless marked otherwise.

1. **Evening items are matched to the wrong night** (`backend/app/routes/lifestyle_impact.py`, activity date = mood timestamp date). Before Sleep items are logged at bedtime on day D. Garmin files the night's sleep under the date of waking (D+1). The page compares the item with day D's sleep, which is the night *before* the item happened. *Owner to confirm against real data on the preview: compare a known night's `sleep_start` with its `sleep_date`.*
2. **HRV uses Garmin's 7-day average** (`weekly_avg`, see `garmin_sync.py` around line 462), so one night's effect is spread over a week and diluted. The raw Garmin response is saved in `GarminHRVDaily.payload` and very likely includes last night's average.
3. **Lopsided comparison.** Each item is compared with the overall average, which includes the days the item happened. It should be days with the item against days without it.
4. **Almost anything counts as an impact.** The threshold is 5% of one standard deviation, and there is no check for chance. The minimum is 3 days.
5. **Outcomes are shown as causes.** Items such as Insomnia or Woke During Night describe the night. They line up with a low sleep score by definition and push real causes out of view.
6. **Twins.** Items that are always logged together get identical results. The app cannot separate them. This is a data limitation; the design should not pretend otherwise (see "Left to the builder").
7. **Headache report: reactions shown as triggers.** A same-day item can be a response to a headache rather than its cause (for example Meditation), and the report can't tell which. The report mixes same-day and day-before items in one list. It also has no confidence measure.
8. **The dashboard daily advice** (`/lifestyle-impact/advice`) recommends whatever tops the flawed Positive list.

## Goals

- Results the owner finds believable: the direction of an effect matches what really happened on those nights.
- Every result shows how sure the app is, and the list is ordered by that confidence.
- Items that aren't possible causes (habits, descriptions of the night, reactions to symptoms) stay out of the impact and trigger lists.
- The owner can correct an item's role in one tap, on the page where the problem shows up.
- Sleep and headache analysis use one shared comparison method and one shared set of item roles.

## Non-goals

- The Analytics page's mood sections. It has the same problems, but it is a later round.
- Any change to how entries are logged on the Mood Entry page.
- Clever statistics that model several items at once. One item at a time is enough for now.
- Medical advice. The app reports patterns in the owner's own data and nothing more.

## Anti-goals (this fails even if it technically works)

- Long lists of "impacts" built on a handful of days.
- Calling something strong when it rests on very few days.
- Treating an unlogged day as "didn't happen" for measures the owner only sometimes logs (hydration).
- Making the owner visit a separate settings area to fix a bad result.
- Losing the owner's existing headache exclude list.

## Delivery

Two stages, released separately so the owner can try stage 1 before stage 2 starts.

- **Stage 1:** shared comparison method, item roles, the redesigned Lifestyle Impact page, and the daily advice fix.
- **Stage 2:** the headache trigger section of the Acupuncture Report moved onto the same method and roles, plus hydration and workouts as possible triggers.

## How it works

### Item roles

Every activity item has one role:

| Role | Meaning | Shown in impact or trigger lists? |
|---|---|---|
| Possible cause | Something that might affect sleep or set off a symptom (alcohol, screen time, caffeine, stress) | Yes |
| Describes the night | An outcome of the night (Insomnia, Woke During Night, Tossing and Turning) | No |
| Symptom | A symptom being explained (Headache and the other Headache Issues items) | No, it is what's being explained |
| Reaction to a symptom | Something done only because of a symptom (e.g. taking a painkiller) | No |
| Just a habit | Recorded for its own sake (Meditation) | No |

**Defaults by tab.** Before Sleep, Lifestyle and Health: possible cause. During Sleep and Morning / Waking Feedback: describes the night. Headache Issues: symptom. The owner only changes the exceptions.

**One role, used everywhere.** Changing an item's role on the sleep page also changes it on the headache report. "Hide from this page only" exists for one-off exceptions.

**Migration.** Every item currently in the headache exclude list (`Activity.ignore_in_reports = true`) becomes "just a habit", so nothing the owner has already excluded comes back.

**Storage.** Roles and per-page hides need to be stored, which probably means a new column or table. This is a data-format change, so the builder must get the owner's approval for it first, as AGENTS.md requires.

### Matching items to nights and days

- **Before Sleep items** count towards the night that follows them, which is the sleep Garmin files under the next day's date.
- **Midday rule:** a Before Sleep item logged between midnight and 12:00 counts as the previous evening, because the owner sometimes logs late or forgets until morning. The owner sometimes moves the time back by hand; that keeps working.
- **During Sleep and Morning items** are logged in the morning and describe the night that has just ended, the same date Garmin uses. No shift.
- **Lifestyle and Health items on the sleep page** happen during day D and count towards the night that follows (sleep date D+1), the same as Before Sleep items. The midday rule applies only to Before Sleep. *(My call.)*
- **Which Garmin value each tab uses** *(my call)*:
  - Sleep Score, Overnight HRV, Resting Heart Rate: the night that follows (sleep date D+1).
  - Overnight Stress: the average stress during sleep for that night, taken from the saved Garmin sleep data if present (look for a field such as `avgSleepStress` in `GarminSleepDaily.payload`). If it's missing, fall back to the all-day stress figure for D+1 and rename the tab "Stress".
  - Steps: the day after (D+1). This answers "does this evening's item affect how active I am the next day".
- **Lifestyle and Health items, for the headache report:** compared on the same day and the day before (see stage 2).
- Use the owner's local time (UK), not UTC, when working out which day an entry belongs to.

### Which nights count as "without"

The owner logs Before Sleep nearly every night (a nightly reminder; about 90–95% consistent). So:

- **If an evening has at least one Before Sleep entry**, every Before Sleep item *not* tapped that evening counts as "without" for that night.
- **If an evening has no Before Sleep entry at all**, the night is treated as unknown for Before Sleep items and left out of their comparison, because it most likely means the owner forgot.
- The same rule applies per tab for Lifestyle and Health items: a day with no entry in that tab is unknown for that tab's items.
- Garmin workouts are the exception (see below): no workout recorded means no workout.

### The comparison

For each possible cause and each measure:

- Compare the average of the measure on nights *with* the item against nights *without* it, within the chosen period.
- **Period buttons: 4 weeks (default), 12 weeks and 26 weeks.** The 7-day option is removed, because with the minimum below it could never show a result (agreed with the owner). The 26-week option is my call, so that rarer items can build up enough nights. The API's current limit of 84 days needs raising to match.
- The effect is the difference, in the measure's own units (points, ms, bpm, steps).
- **Too early to tell:** fewer than 5 nights with the item, or fewer than 5 without. Shown in a separate group with the count so far. *(Builder's call within reason; the owner accepted 5 as a starting point.)*
- **Confidence: three levels, Strong, Some evidence and Weak.** It must take into account both the number of nights on each side and how consistent the difference is, not just the size of the difference. The exact test is left to the builder (see below), but it must be explainable in one sentence on the page.
- Results whose difference is too small to matter (inside normal night-to-night variation) are dropped from the list, not shown as "minimal impact".
- HRV uses last night's value, not the weekly average.

### Measures with gaps: hydration

Hydration comes from Garmin (ml drunk and a daily goal, stored in `GarminHydrationDaily`). The owner only logs it some days.

- A day with 0 ml or no record means **unknown**, not "didn't drink". It is left out completely.
- Compare by amount, not yes/no: hydration as a percentage of that day's goal, because the goal changes daily.
- The same "missing means unknown" rule applies to any other measure that depends on the owner logging it.

### Workouts as possible causes (both stages)

Garmin workouts are already stored (`GarminActivity`: date, start time, type, duration). They appear in the lists as possible causes alongside logged items, compared the same way:

- **Workout that day:** whether there was one on day D, compared with the night that follows (D+1). Unlike activity items, a day with no workout recorded really does mean "no workout", because the watch records them automatically.
- **Late workout:** a workout that started after 18:00, kept as a separate entry because exercise close to bedtime affects sleep differently. *(The 18:00 cut-off is my call.)*
- **Longer workouts:** whether duration makes a difference (for example, over and under 45 minutes) is left to the builder, as long as it uses the same confidence rules.
- On the headache report, the same entries are checked for the day before a symptom day.

### Lifestyle Impact page (stage 1)

Mockup agreed in brainstorming (option B, version 2). It must follow DESIGN.md and `frontend-web/src/tokens.css`.

- Period buttons become 4w (default), 12w and 26w. Keep the measure tabs (Overnight Stress, Overnight HRV, Sleep Score, Resting Heart Rate, Steps), and the average figure.
- Replace the Positive / Negative / Minimal columns with **one ranked list**: "What seems to affect your [measure]".
- Each row:
  - item name
  - the effect, e.g. "−11 points", in **green if it's better for the owner and red if worse**. Colour depends on the measure's direction (lower stress and lower resting heart rate are better), not on the sign.
  - "N nights with, M without"
  - on the right: a **3-bar confidence meter plus a word** (Strong / Some evidence / Weak)
  - a **⋯ button**
- **Order:** by confidence first (Strong, then Some evidence, then Weak), then by size of effect within each level. The owner explicitly prefers a confident small effect over a big unconfident one.
- **Too early to tell** group at the bottom: item name and "3 nights so far, needs at least 5".
- **⋯ menu** asks "What is [item] for you?" and offers: Just a habit I'm recording / Describes how the night went / Something I do because of a symptom / Hide from this page only. Changes take effect straight away.
- **Left out of this page** section at the bottom: chips showing each excluded item and why, with × to bring it back.
- A one-line plain-English note on how to read the page.
- Mobile layout must work. The owner logs from their phone.

### Daily advice (stage 1)

- Only mention items rated Strong or Some evidence.
- Can suggest avoiding a harmful item as well as doing a helpful one, e.g. "Alcohol has lowered your sleep score by about 11 points on average. Worth skipping tonight."
- If nothing qualifies, fall back to the current general messages.

### Headache report (stage 2)

Acupuncture & Symptom Report page. Keep the timeframe controls, the acupuncture session picker and the symptom-day summary cards as they are.

- Uses the same roles, the same with/without comparison, the same confidence levels and the same row design, including the ⋯ menu. The current "Exclude Activities" section is replaced by the "Left out of this page" chips.
- **Main list: "Possible triggers (the day and night before)".** Possible causes from the day before a symptom day, compared with the day before a symptom-free day. Before Sleep items follow the matching rules above.
- **Separate, clearly labelled list: "Same day: could be a cause or a reaction".** Same-day items, kept apart so reactions can't pass as triggers.
- **Garmin measures from the night or day before:** sleep score, last-night HRV, stress and resting heart rate (already partly in `reports.py`), plus:
  - **Hydration** as % of goal, using only logged days (see above).
  - **Workouts the day before:** whether there was one and its duration. Garmin activities are already stored (`GarminActivity`). The owner confirmed this matters.
- **Physio (Home) and Physio stay possible causes.** The owner does neck and shoulder exercises that could themselves set off a headache, so physio the day before is a genuine trigger to check. Same-day physio still goes in the "same day" list, because it may be done in response to a headache.
- **Symptom days come from the Symptom role**, not from matching names as `reports.py` does now (it searches for "headache", "migraine" and "jaw"). Migration: every item the current name match catches, plus every item in the Headache Issues tab, gets the Symptom role, so the symptom days stay the same on the day of release. The ⋯ menu doesn't offer "symptom" in this version. *(My call.)*

## Constraints

- The repo is public. No real personal data or figures in code, tests, fixtures or docs. Use made-up data.
- The process in AGENTS.md and the `safe-change` skill applies: branch, backend tests against a throwaway Postgres, preview with a copy of live data, owner go-ahead before merging.
- Any schema or data-format change needs the owner's approval before it's built.
- Visual changes wait until the owner is home to check them (global rules).
- Follow the "Quiet Sanctuary" design language in DESIGN.md and the existing tokens.

## Left to the builder

- The exact statistical method behind the three confidence levels (for example a permutation test, a t-test or a bootstrap) and its cut-offs, as long as it accounts for sample size and consistency and can be explained in one sentence.
- The "too small to matter" cut-off.
- Whether last-night HRV is read from the saved payload or stored in a new column (a new column needs owner approval).
- How twins (items always logged together) are handled, for example a note saying "always logged with Bathroom, can't be separated". A note is fine; hiding one of the pair silently is not.
- API shape and how the shared comparison code is organised between `lifestyle_impact.py` and `reports.py`.
- Tests: the "unknown evening" rule, the matching rules (midday rule, Garmin wake-date offset), the with/without comparison, confidence ordering, "missing means unknown" for hydration, and role filtering all need backend tests with made-up data.
