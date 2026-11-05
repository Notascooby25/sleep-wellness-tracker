# Changelog

## 4.20.2 (2026-11-05)

**Lifestyle impact improvements and independent headache tracking.** Updating an item's role or hiding it on the Lifestyle Impact page now only affects that page, leaving potential triggers untouched on the headache report. Midnight workouts (between midnight and 04:00) now correctly count towards the night underway and are tagged as late workouts. Fixed summertime local timestamp handling on Garmin workouts so evening workouts are not recorded an hour early. Added support for alternative Garmin HRV payload structures, bounded workout comparisons to active tracking periods, and protected database startup migrations with `IF NOT EXISTS` for worker safety.

## 4.20.1 (2026-11-05)

**Readable exports and reliable CSV downloads.** Fixed an issue where downloading CSV data exports from Settings could fail with a stream error (`body stream is locked`). In the Mood Log Tools page, data exports (CSV, JSON, and full backups) now include human-readable activity and category names alongside database IDs so backup files are easy to read and understand.

## 4.20.0 (2026-11-02)

**Lifestyle Impact you can trust.** The page now matches each evening item (alcohol, screens, caffeine and so on) to the night's sleep that follows it, not the night before. It compares nights with the item against nights without it, and it uses last night's HRV and stress during sleep, not weekly or all-day averages. Each result shows how sure the app is (Strong, Some evidence or Weak), and results are ordered by that. Items with too few nights wait in a "Too early to tell" list. Garmin workouts are included.

You can mark any item, straight from its row, as "just a habit", "describes the night" or "something I do because of a symptom", and bring it back later. Old and new copies of the same item count as one. Your existing headache exclude list carries over.

The dashboard's daily advice now only mentions results the app has real evidence for. The 7-day view has been replaced by 4, 12 and 26 weeks.
