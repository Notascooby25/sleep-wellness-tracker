with open('frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte', 'r') as f:
    content = f.read()

content = content.replace(
    "metric: 'sleep_score' | 'overnight_hrv' | 'overnight_stress';",
    "metric: 'sleep_score' | 'overnight_hrv' | 'overnight_stress' | 'resting_heart_rate' | 'steps';"
)

with open('frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte', 'w') as f:
    f.write(content)
