with open('frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte', 'r') as f:
    content = f.read()

new_options = """    { value: 'overnight_stress', label: 'Overnight Stress' },
    { value: 'overnight_hrv', label: 'Overnight HRV' },
    { value: 'sleep_score', label: 'Sleep Score' },
    { value: 'resting_heart_rate', label: 'Resting Heart Rate' },
    { value: 'steps', label: 'Steps' }
  ] as const;"""

old_options = """    { value: 'overnight_stress', label: 'Overnight Stress' },
    { value: 'overnight_hrv', label: 'Overnight HRV' },
    { value: 'sleep_score', label: 'Sleep Score' }
  ] as const;"""

content = content.replace(old_options, new_options)

with open('frontend-web/src/routes/garmin-lifestyle-impact/+page.svelte', 'w') as f:
    f.write(content)
