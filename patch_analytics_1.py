with open('frontend-web/src/routes/analytics/+page.svelte', 'r') as f:
    content = f.read()

# Add variables
content = content.replace(
    "let hrvRows: Array<Record<string, unknown>> = [];",
    "let hrvRows: Array<Record<string, unknown>> = [];\n  let rhrRows: Array<Record<string, unknown>> = [];\n  let stressRows: Array<Record<string, unknown>> = [];\n  let stepsRows: Array<Record<string, unknown>> = [];"
)

# Update Promise.all
content = content.replace(
    "const [moodData, sleepWrap, bodyWrap, hrvWrap, acts, cats] = await Promise.all([",
    "const [moodData, sleepWrap, bodyWrap, hrvWrap, rhrWrap, stressWrap, stepsWrap, acts, cats] = await Promise.all(["
)
content = content.replace(
    "getJson<GarminRows>(`/garmin/hrv/range?start_date=${fromDate}&end_date=${toDate}`),",
    "getJson<GarminRows>(`/garmin/hrv/range?start_date=${fromDate}&end_date=${toDate}`),\n        getJson<GarminRows>(`/garmin/resting-heart-rate/range?start_date=${fromDate}&end_date=${toDate}`),\n        getJson<GarminRows>(`/garmin/stress/range?start_date=${fromDate}&end_date=${toDate}`),\n        getJson<GarminRows>(`/garmin/steps/range?start_date=${fromDate}&end_date=${toDate}`),"
)

# Set rows
content = content.replace(
    "hrvRows = hrvWrap?.data || [];",
    "hrvRows = hrvWrap?.data || [];\n      rhrRows = rhrWrap?.data || [];\n      stressRows = stressWrap?.data || [];\n      stepsRows = stepsWrap?.data || [];"
)

# Add Maps
content = content.replace(
    "$: hrvByDateMap = new Map(hrvRows.map((r) => [String(r.date), r]));",
    "$: hrvByDateMap = new Map(hrvRows.map((r) => [String(r.date), r]));\n  $: rhrByDateMap = new Map(rhrRows.map((r) => [String(r.date), r]));\n  $: stressByDateMap = new Map(stressRows.map((r) => [String(r.date), r]));\n  $: stepsByDateMap = new Map(stepsRows.map((r) => [String(r.date), r]));"
)

with open('frontend-web/src/routes/analytics/+page.svelte', 'w') as f:
    f.write(content)
