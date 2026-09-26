import re

with open('backend/app/routes/lifestyle_impact.py', 'r') as f:
    content = f.read()

# Add to _METRIC_CONFIG
new_metrics = """    "resting_heart_rate": {
        "model": models.GarminRestingHeartRateDaily,
        "date_field": models.GarminRestingHeartRateDaily.heart_rate_date,
        "value_field": models.GarminRestingHeartRateDaily.resting_heart_rate,
        "higher_is_better": False,
        "label": "resting heart rate",
    },
    "steps": {
        "model": models.GarminStepsDaily,
        "date_field": models.GarminStepsDaily.steps_date,
        "value_field": models.GarminStepsDaily.total_steps,
        "higher_is_better": True,
        "label": "steps",
    },
}"""
content = content.replace("    },\n}", "    },\n" + new_metrics)

# Update Query pattern
content = re.sub(
    r'pattern="\^\(sleep_score\|overnight_hrv\|overnight_stress\)\$"',
    r'pattern="^(sleep_score|overnight_hrv|overnight_stress|resting_heart_rate|steps)$"',
    content
)

with open('backend/app/routes/lifestyle_impact.py', 'w') as f:
    f.write(content)
