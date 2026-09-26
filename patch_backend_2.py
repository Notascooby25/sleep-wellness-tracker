import re

with open('backend/app/routes/lifestyle_impact.py', 'r') as f:
    content = f.read()

content = content.replace(
    ".options(selectinload(models.Mood.activities).selectinload(models.Activity.category))",
    ".options(selectinload(models.Mood.activities).selectinload(models.Activity.category), selectinload(models.Mood.activity_details))"
)

old_loop = """    activity_dates: dict[str, set[dt.date]] = defaultdict(set)
    for mood in mood_rows:
        mood_date = mood.timestamp.date()
        for activity in mood.activities:
            if not _is_sleep_category(activity.category.name if activity.category else None):
                continue
            name = (activity.name or "").strip()
            if name:
                activity_dates[name].add(mood_date)"""

new_loop = """    activity_dates: dict[str, set[dt.date]] = defaultdict(set)
    for mood in mood_rows:
        mood_date = mood.timestamp.date()
        detail_map = {d.activity_id: d for d in mood.activity_details}
        for activity in mood.activities:
            if not _is_sleep_category(activity.category.name if activity.category else None):
                continue
            name = (activity.name or "").strip()
            if name:
                det = detail_map.get(activity.id)
                if det:
                    if det.quantity_numeric is not None:
                        name = f"{name} (Qty: {det.quantity_numeric:g})"
                    elif det.severity is not None:
                        name = f"{name} (Sev: {det.severity})"
                activity_dates[name].add(mood_date)"""

content = content.replace(old_loop, new_loop)

with open('backend/app/routes/lifestyle_impact.py', 'w') as f:
    f.write(content)
