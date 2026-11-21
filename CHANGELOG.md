# Changelog

## 4.23.0 (2026-11-21)

**Weather follows you when you travel, and your weather history is now safe.** When you save an entry or answer "Headache today?" more than 25 km from home, the app notes roughly where you were that day (to about 1 km, and only for today or yesterday, never for older days you fill in later) and uses the weather there instead of at home. The weather for days away is fetched in the background, a few days at a time. Until it arrives, those days are left out of the weather checks rather than wrongly given the weather at home. Days away now show a small line along the bottom of the headache report's day strip, with an "Away from home" label when you tap the day. Changing your home area in Settings now asks you to confirm and no longer deletes the weather already stored for past days. You only need it if you move house.

## 4.22.0 (2026-11-21)

**Headache causes found more accurately: a daily "Headache today?" check, plus weather and more sleep measures.** Mood Entry now opens with a one-tap "Headache today?" card. Your answer decides whether a day counts as a headache day or a clear day, so a forgotten headache no longer counts as clear, and items like Brain Fog no longer make a day a headache day on their own. If you answer Yes, you pick when it started (woke with it, morning, afternoon or evening), and anything logged after it started is no longer treated as a possible same-day cause. Days without an answer still work as before. The report says how many days were confirmed, and the day strip shows your answer and start time. Settings has a new "Weather for the headache report" card: tap "Use my current location as home" once and the app fetches daily air pressure and temperature for your whole history (only a rough position, to about 1 km, is stored), then keeps it topped up. The trigger report now also checks the change in air pressure since yesterday, the day's highest temperature, sleep length, bedtime and wake-up time compared with your usual, and Body Battery on waking. There's also a one-tap 21:00 "Headache check" reminder in Settings.

## 4.21.15 (2026-11-19)

**Acupuncture report redesigned as a quick "Clinic Brief", and the trigger-finding made more trustworthy.** The page now opens with headline numbers for the appointment period (headache days, migraine days and other headache-type items, each counted once per day) with a badge showing the change since last time, a clickable strip of days with acupuncture days marked, and bar charts for headache types and head positions. Things you didn't log in the period are hidden. A switch lets you look for triggers over this period, the last 90 days or all time, with a plain-English verdict on whether there's a real pattern or it looks like chance. The trigger logic was fixed: days you didn't log are no longer treated as "nothing happened", "Before Sleep" items only count as a possible cause for the next day, things you log because of a headache (like painkillers) are no longer treated as triggers, and results are corrected for chance findings, with tiny effects listed separately as "no clear link". The "since last appointment" quick-select and date pickers are kept, and the old report link still works. Date ranges over 2 years are now politely refused instead of slowing the page down.

## 4.21.14 (2026-11-17)

**Proper page headings for screen readers.** Each page's title is now its main heading (the site name in the header used to be the main heading on every page, so screen reader users never heard what page they were on). The pages look exactly the same as before.

## 4.21.13 (2026-11-17)

**Tidier error replies.** When the app's server can't reach its database service, it used to send the browser a technical error string that could include an internal address. It now sends a plain fixed message and keeps the technical detail in its own log. No visible change.

## 4.21.12 (2026-11-17)

**Clearer messages when something goes wrong.** Instead of technical text like `TypeError: Failed to fetch` or `422 {"detail":…}`, every page now says what happened and what to do, for example "You appear to be offline or the server can't be reached. Check your connection and try again." or "That took too long. Please try again." If your session has ended, the app now takes you to the sign-in page and brings you back to where you were. Error and status messages are also read out by screen readers. Analytics shows "Loading your analytics…" with a "Try again" button if it fails, and Manage Activities, Manage Categories and the Mood Log delete button can no longer be pressed twice while they're working. The login page's redirect only ever goes to a page inside the app.

## 4.21.11 (2026-11-17)

**Accessibility tidy-up.** If your phone or computer is set to "reduce motion", the app no longer spins, slides or shimmers (colour changes and loading text still work). The Mood Log filter box now shows the same clear dark outline as everything else when you click into it. Buttons are marked as plain buttons so they can never submit a form by accident, the Mood Log table now has proper column labels for screen readers, and the login page puts the cursor in the password box in a cleaner way. Nothing else changes in how the app looks.

## 4.21.10 (2026-11-17)

**Security housekeeping for the website's building blocks.** The saved list of exact software versions the web app is built from (the "lock file") was out of date, so GitHub's scanner reported 28 vulnerability alerts against versions the app isn't actually built with. The lock file is refreshed to the current safe versions, and the app's build now follows it exactly, so what GitHub scans is what runs. No change to how the app looks or behaves.

## 4.21.9 (2026-11-17)

**Consistent shades of blue.** About 50 slightly different shades of blue and grey that were typed out separately across the pages are now taken from the shared colour list. Each one moved to its nearest named colour, by a difference too small to notice at a glance (the largest is about the gap between two neighbouring paint swatches). Status and chart colours (greens, ambers, reds) were left as they were. Nothing else changes.

## 4.21.8 (2026-11-17)

**Behind-the-scenes colour tidy-up (no visible change).** The app's colours are now read from one shared list (`tokens.css`) in 125 places instead of being typed out again each time, and six new named colours were added for links, errors and confirmations. Every colour keeps exactly the same value, so the app should look identical. This prepares for making similar shades consistent in a later release.

## 4.21.7 (2026-11-17)

**Repository tidy-up.** Removed 18 leftover one-off files from the top of the project (old `patch_*` scripts, scratch test scripts, an empty-data backup stub and a spare import script). Nothing in the app, its build, its tests or its deployment used them, and they remain in the project's history if ever needed. No change to how the app behaves.

## 4.21.6 (2026-11-17)

**Test release for the "new version available" bar.** No visible changes. This release only exists to check that the bar appears for someone who still has 4.21.5 open.

## 4.21.5 (2026-11-17)

**"New version available" bar.** When a new version of the app has been released, a bar now appears under the menu saying so, with an "Update now" button. Tapping it refreshes the app and loads the new version. It checks every 5 minutes and whenever you switch back to the app, and it never reloads on its own, so anything you're typing is never lost.

## 4.21.4 (2026-11-17)

**DM Sans font now actually loads.** The app was designed around the DM Sans font but never loaded it, so every device showed its own fallback font. The font is now stored inside the app itself (no request to Google or any outside site) and used everywhere, so text looks the same on every device. Text may be very slightly wider than before, and nothing else changes.

## 4.21.3 (2026-11-17)

**Accessibility basics.** Keyboard focus outlines are now dark blue, so you can see where you are (they were too pale to see clearly). Every page now has its own browser tab title, such as "Mood Log · Sleep Wellness Tracker". The menu is labelled as the main navigation and marks the current page for screen readers, the offline banner is announced, and on touch screens the menu buttons are taller (44px) and easier to tap. No data or layout changes on desktop.

## 4.21.2 (2026-11-07)

**Require Last Night's Sleep rating on Morning Feedback.** When selecting activities under the "Morning / Waking Feedback" category, the sleep rating is now required before saving. An inline reminder appears above the Save Entry button if a rating is still missing, and attempting to save without a rating shows a clear guidance message and automatically scrolls smoothly up to the rating pills.

## 4.21.1 (2026-11-05)

**Fix acupuncture report activity settings and left-out item restoration.** Fixed an issue where selecting "Hide from this page only" on the Acupuncture & Symptom Report failed with a 422 error by allowing `acupuncture_report` in the activity settings validation schema. Fixed the "Left out of this page" section so default morning and night feedback items (such as "Woke up tired") do not falsely flood the chip list unless explicitly customized, and clicking the × button on excluded chips successfully restores and removes them.

## 4.21.0 (2026-11-05)

**Headache and symptom tracking you can trust.** The Acupuncture & Symptom Report now uses the same trustworthy comparison method and Quiet Sanctuary design introduced for sleep impact. It identifies symptom days automatically from activities marked as symptoms (including migraines, headaches, and jaw pain) and compares them against symptom-free days.

Triggers are divided into causes from the day and evening before (including Garmin workouts and biometrics like sleep score, overnight stress, HRV, resting heart rate, and hydration) and same-day events (kept separate so treatments like painkillers are not mistaken for causes). Each result shows confidence bars (Strong, Some evidence, Weak) backed by statistical permutation testing and multiple-testing corrections. Items with fewer than 5 days wait in "Too early to tell", and items you choose to exclude appear as restoreable chips under "Left out of this page".

## 4.20.2 (2026-11-05)

**Lifestyle impact improvements and independent headache tracking.** Updating an item's role or hiding it on the Lifestyle Impact page now only affects that page, leaving potential triggers untouched on the headache report. Midnight workouts (between midnight and 04:00) now correctly count towards the night underway and are tagged as late workouts. Fixed summertime local timestamp handling on Garmin workouts so evening workouts are not recorded an hour early. Added support for alternative Garmin HRV payload structures, bounded workout comparisons to active tracking periods, and protected database startup migrations with `IF NOT EXISTS` for worker safety.

## 4.20.1 (2026-11-05)

**Readable exports and reliable CSV downloads.** Fixed an issue where downloading CSV data exports from Settings could fail with a stream error (`body stream is locked`). In the Mood Log Tools page, data exports (CSV, JSON, and full backups) now include human-readable activity and category names alongside database IDs so backup files are easy to read and understand.

## 4.20.0 (2026-11-02)

**Lifestyle Impact you can trust.** The page now matches each evening item (alcohol, screens, caffeine and so on) to the night's sleep that follows it, not the night before. It compares nights with the item against nights without it, and it uses last night's HRV and stress during sleep, not weekly or all-day averages. Each result shows how sure the app is (Strong, Some evidence or Weak), and results are ordered by that. Items with too few nights wait in a "Too early to tell" list. Garmin workouts are included.

You can mark any item, straight from its row, as "just a habit", "describes the night" or "something I do because of a symptom", and bring it back later. Old and new copies of the same item count as one. Your existing headache exclude list carries over.

The dashboard's daily advice now only mentions results the app has real evidence for. The 7-day view has been replaced by 4, 12 and 26 weeks.
