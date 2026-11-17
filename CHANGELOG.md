# Changelog

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
