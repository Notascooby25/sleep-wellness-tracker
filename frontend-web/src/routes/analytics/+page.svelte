<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';
  import type { Activity, Category, MoodEntry } from '$lib/types';

  type GarminRows = { data: Array<Record<string, unknown>> };

  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  let fromDate = monthAgo;
  let toDate = today;
  let quickRange = 'Last 30 days';
  let mode: 'Core' | 'Core + one extra' = 'Core';
  let extraSection: 'Recovery Metrics' | 'Mood Distribution' | 'Activity Log' = 'Recovery Metrics';

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
  let categories: Category[] = [];
  let sleepRows: Array<Record<string, unknown>> = [];
  let bodyRows: Array<Record<string, unknown>> = [];
  let hrvRows: Array<Record<string, unknown>> = [];
  let status = '';

  let selectedActivity = '';

  const avg = (numbers: number[]) => (numbers.length ? numbers.reduce((a, b) => a + b, 0) / numbers.length : null);
  const avgOfNullable = (numbers: Array<number | null>) => {
    const clean = numbers.filter((n): n is number => n !== null && Number.isFinite(n));
    return clean.length ? clean.reduce((a, b) => a + b, 0) / clean.length : null;
  };
  const pctDiffLowerIsBetter = (withValue: number | null, withoutValue: number | null) => {
    if (withValue === null || withoutValue === null || withoutValue === 0) return null;
    return ((withoutValue - withValue) / withoutValue) * 100;
  };
  const confidenceLabel = (withCount: number, withoutCount: number) => {
    const minSide = Math.min(withCount, withoutCount);
    if (minSide >= 20) return 'High';
    if (minSide >= 8) return 'Medium';
    return 'Low';
  };

  const ukDate = (iso: string) => new Date(iso).toLocaleDateString('en-CA', { timeZone: 'Europe/London' });

  const applyQuickRange = () => {
    const daysMap: Record<string, number> = {
      'Last 7 days': 7,
      'Last 14 days': 14,
      'Last 30 days': 30,
      'Last 90 days': 90,
    };
    if (!daysMap[quickRange]) return;
    const days = daysMap[quickRange];
    const start = new Date(Date.now() - (days - 1) * 86400000).toISOString().slice(0, 10);
    fromDate = start;
    toDate = today;
  };

  const load = async () => {
    status = '';
    try {
      const [moodData, sleepWrap, bodyWrap, hrvWrap, acts, cats] = await Promise.all([
        getJson<MoodEntry[]>(`/mood/?from_date=${fromDate}&to_date=${toDate}`),
        getJson<GarminRows>(`/garmin/sleep/range?start_date=${fromDate}&end_date=${toDate}`),
        getJson<GarminRows>(`/garmin/body-battery/range?start_date=${fromDate}&end_date=${toDate}`),
        getJson<GarminRows>(`/garmin/hrv/range?start_date=${fromDate}&end_date=${toDate}`),
        getJson<Activity[]>('/activities/'),
        getJson<Category[]>('/categories/'),
      ]);
      entries = moodData;
      sleepRows = sleepWrap?.data || [];
      bodyRows = bodyWrap?.data || [];
      hrvRows = hrvWrap?.data || [];
      activities = acts;
      categories = cats;
      if (!selectedActivity) {
        const names = Array.from(new Set(activities.map(a => a.name))).sort();
        selectedActivity = names[0] || '';
      }
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  const getSeriesPath = (values: Array<number | null>, width: number, height: number): string => {
    const pts = values
      .map((v, i) => ({ i, v }))
      .filter((p) => p.v !== null) as Array<{ i: number; v: number }>;
    if (pts.length < 2) return '';
    const ys = pts.map((p) => p.v);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const span = Math.max(1e-6, maxY - minY);
    return pts
      .map((p, idx) => {
        const x = (p.i / Math.max(1, values.length - 1)) * width;
        const y = height - ((p.v - minY) / span) * height;
        return `${idx === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
      })
      .join(' ');
  };

  $: sleepByDateMap = new Map(sleepRows.map((r) => [String(r.date), r]));
  $: bodyByDateMap = new Map(bodyRows.map((r) => [String(r.date), r]));
  $: hrvByDateMap = new Map(hrvRows.map((r) => [String(r.date), r]));

  $: rated = entries.filter((e) => e.mood_score !== null).map((e) => Number(e.mood_score));
  $: sleepScores = sleepRows.map((r) => Number(r.sleep_score)).filter((n) => Number.isFinite(n));
  $: avgMood = avg(rated);
  $: avgSleepScore = avg(sleepScores);

  $: avgSleepMins = avg(
    sleepRows
      .map((r) => Number(r.total_sleep_minutes))
      .filter((n) => Number.isFinite(n))
  );

  $: avgHrv = avg(
    hrvRows
      .map((r) => Number(r.weekly_avg))
      .filter((n) => Number.isFinite(n))
  );

  $: dayList = (() => {
    const start = new Date(fromDate + 'T00:00:00');
    const end = new Date(toDate + 'T00:00:00');
    const days: string[] = [];
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      days.push(d.toISOString().slice(0, 10));
    }
    return days;
  })();

  $: dailyMoodMap = (() => {
    const map = new Map<string, number[]>();
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const d = ukDate(e.timestamp);
      if (!map.has(d)) map.set(d, []);
      map.get(d)!.push(Number(e.mood_score));
    }
    return new Map(Array.from(map.entries()).map(([k, arr]) => [k, arr.reduce((a, b) => a + b, 0) / arr.length]));
  })();

  $: moodTrendValues = dayList.map((d) => dailyMoodMap.get(d) ?? null);

  $: bestDay = (() => {
    const pairs = Array.from(dailyMoodMap.entries());
    if (!pairs.length) return null;
    return pairs.reduce((best, p) => (p[1] < best[1] ? p : best), pairs[0]);
  })();

  $: worstDay = (() => {
    const pairs = Array.from(dailyMoodMap.entries());
    if (!pairs.length) return null;
    return pairs.reduce((worst, p) => (p[1] > worst[1] ? p : worst), pairs[0]);
  })();

  $: sleepMoodDates = dayList.filter((d) => sleepByDateMap.has(d) && dailyMoodMap.has(d));
  $: sleepScoreSeries = sleepMoodDates.map((d) => Number(sleepByDateMap.get(d)?.sleep_score ?? null));
  $: sleepDurationSeries = sleepMoodDates.map((d) => {
    const m = Number(sleepByDateMap.get(d)?.total_sleep_minutes);
    return Number.isFinite(m) ? m / 60 : null;
  });
  $: moodOnSleepDates = sleepMoodDates.map((d) => dailyMoodMap.get(d) ?? null);

  $: recoveryDates = dayList;
  $: hrvSeries = recoveryDates.map((d) => {
    const n = Number(hrvByDateMap.get(d)?.weekly_avg);
    return Number.isFinite(n) ? n : null;
  });
  $: batterySeries = recoveryDates.map((d) => {
    const n = Number(bodyByDateMap.get(d)?.end_of_day_value);
    return Number.isFinite(n) ? n : null;
  });

  $: moodCountByScore = [1, 2, 3, 4, 5].map((s) => rated.filter((r) => r === s).length);

  $: moodByHour = (() => {
    const perHour = new Map<number, number[]>();
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const h = new Date(e.timestamp).getHours();
      if (!perHour.has(h)) perHour.set(h, []);
      perHour.get(h)!.push(Number(e.mood_score));
    }
    return Array.from(perHour.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([h, arr]) => ({ hour: h, avg: arr.reduce((x, y) => x + y, 0) / arr.length }));
  })();

  $: activityById = new Map(activities.map((a) => [a.id, a]));
  $: categoryById = new Map(categories.map((c) => [c.id, c]));

  $: sleepCategoryIds = new Set(
    categories
      .filter((c) => {
        const n = c.name.toLowerCase();
        return n.includes('before sleep') || n.includes('during sleep') || n.includes('pre-sleep') || n.includes('presleep');
      })
      .map((c) => c.id)
  );

  $: activityStats = (() => {
    const map = new Map<string, { count: number; moods: number[] }>();
    for (const e of entries) {
      for (const aid of e.activity_ids || []) {
        const name = activityById.get(aid)?.name || `#${aid}`;
        if (!map.has(name)) map.set(name, { count: 0, moods: [] });
        const row = map.get(name)!;
        row.count += 1;
        if (e.mood_score !== null && e.mood_score !== undefined) row.moods.push(Number(e.mood_score));
      }
    }
    return Array.from(map.entries())
      .map(([name, v]) => ({
        name,
        count: v.count,
        avgMood: v.moods.length ? v.moods.reduce((a, b) => a + b, 0) / v.moods.length : null
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);
  })();

  $: selectedActivityStats = (() => {
    if (!selectedActivity) return null;
    const selectedIds = new Set(activities.filter((a) => a.name === selectedActivity).map((a) => a.id));
    if (selectedIds.size === 0) return null;
    const withDates = new Set<string>();
    for (const e of entries) {
      const has = (e.activity_ids || []).some((id: number) => selectedIds.has(id));
      if (has) withDates.add(ukDate(e.timestamp));
    }

    const scoreWith: Array<number | null> = [];
    const scoreOther: Array<number | null> = [];
    const totalWith: Array<number | null> = [];
    const totalOther: Array<number | null> = [];
    const withEntryMoods: number[] = [];
    const withoutEntryMoods: number[] = [];

    const weekdayCounts = [0, 0, 0, 0, 0, 0, 0];
    for (const d of withDates) {
      const day = new Date(d + 'T12:00:00').getDay();
      weekdayCounts[day] += 1;
    }

    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const has = (e.activity_ids || []).some((id: number) => selectedIds.has(id));
      if (has) withEntryMoods.push(Number(e.mood_score));
      else withoutEntryMoods.push(Number(e.mood_score));
    }

    for (const d of dayList) {
      const row = sleepByDateMap.get(d);
      const score = row ? Number(row.sleep_score) : null;
      const total = row ? Number(row.total_sleep_minutes) / 60 : null;
      if (withDates.has(d)) {
        scoreWith.push(Number.isFinite(score as number) ? score : null);
        scoreOther.push(null);
        totalWith.push(Number.isFinite(total as number) ? total : null);
        totalOther.push(null);
      } else {
        scoreWith.push(null);
        scoreOther.push(Number.isFinite(score as number) ? score : null);
        totalWith.push(null);
        totalOther.push(Number.isFinite(total as number) ? total : null);
      }
    }

    const sameDayWithMoods = Array.from(withDates)
      .map((d) => dailyMoodMap.get(d) ?? null)
      .filter((n): n is number => n !== null);
    const sameDayWithoutMoods = dayList
      .filter((d) => !withDates.has(d))
      .map((d) => dailyMoodMap.get(d) ?? null)
      .filter((n): n is number => n !== null);

    const previousDayMoods = Array.from(withDates)
      .map((d) => {
        const x = new Date(d + 'T12:00:00');
        x.setDate(x.getDate() - 1);
        return dailyMoodMap.get(x.toISOString().slice(0, 10)) ?? null;
      })
      .filter((n): n is number => n !== null);

    const nextDayMoods = Array.from(withDates)
      .map((d) => {
        const x = new Date(d + 'T12:00:00');
        x.setDate(x.getDate() + 1);
        return dailyMoodMap.get(x.toISOString().slice(0, 10)) ?? null;
      })
      .filter((n): n is number => n !== null);

    const withWithoutPct = pctDiffLowerIsBetter(avg(withEntryMoods), avg(withoutEntryMoods));
    const previousDayPct = pctDiffLowerIsBetter(avg(previousDayMoods), avg(sameDayWithoutMoods));
    const sameDayPct = pctDiffLowerIsBetter(avg(sameDayWithMoods), avg(sameDayWithoutMoods));
    const nextDayPct = pctDiffLowerIsBetter(avg(nextDayMoods), avg(sameDayWithoutMoods));

    let longestWith = 0;
    let longestWithout = 0;
    let runWith = 0;
    let runWithout = 0;
    for (const d of dayList) {
      if (withDates.has(d)) {
        runWith += 1;
        runWithout = 0;
      } else {
        runWithout += 1;
        runWith = 0;
      }
      if (runWith > longestWith) longestWith = runWith;
      if (runWithout > longestWithout) longestWithout = runWithout;
    }

    return {
      withCount: withDates.size,
      otherCount: Math.max(0, dayList.length - withDates.size),
      scoreWith,
      scoreOther,
      totalWith,
      totalOther,
      withWithoutPct,
      previousDayPct,
      sameDayPct,
      nextDayPct,
      confidence: confidenceLabel(withEntryMoods.length, withoutEntryMoods.length),
      weekdayCounts,
      longestWith,
      longestWithout,
      avgScoreWith: avgOfNullable(scoreWith),
      avgScoreOther: avgOfNullable(scoreOther),
      avgTotalWith: avgOfNullable(totalWith),
      avgTotalOther: avgOfNullable(totalOther),
    };
  })();

  const hoursMins = (minutes: number | null) => {
    if (minutes === null || Number.isNaN(minutes)) return '-';
    const mins = Math.round(minutes);
    return `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, '0')}m`;
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Analytics</h2>
  <p>Trends and insights across mood, sleep, and Garmin wellness data.</p>
</section>

<section class="card">
  <div class="controls">
    <label>
      <div class="label">From</div>
      <input type="date" bind:value={fromDate} />
    </label>
    <label>
      <div class="label">To</div>
      <input type="date" bind:value={toDate} />
    </label>
    <label>
      <div class="label">Quick range</div>
      <select bind:value={quickRange} on:change={applyQuickRange}>
        <option>Last 7 days</option>
        <option>Last 14 days</option>
        <option selected>Last 30 days</option>
        <option>Last 90 days</option>
      </select>
    </label>
    <div class="btn-row">
      <button on:click={load}>Refresh</button>
    </div>
  </div>

  <div class="controls" style="margin-top:0.7rem;">
    <label>
      <div class="label">Display</div>
      <select bind:value={mode}>
        <option>Core</option>
        <option>Core + one extra</option>
      </select>
    </label>
    <label>
      <div class="label">Extra section</div>
      <select bind:value={extraSection} disabled={mode !== 'Core + one extra'}>
        <option>Recovery Metrics</option>
        <option>Mood Distribution</option>
        <option>Activity Log</option>
      </select>
    </label>
  </div>
  {#if status}<p class="status">{status}</p>{/if}

  <div class="legend-box">
    <div class="legend-title">How to read this</div>
    <div class="legend-grid">
      <span><b>Mood scale:</b> lower is better (1 = great, 5 = struggling).</span>
      <span><b>Effect %:</b> positive means better mood with the activity.</span>
      <span><b>Confidence:</b> High (20+ each side), Medium (8+), Low (&lt;8).</span>
      <span><b>Lines:</b> dark blue = selected group, light blue = comparison, red = mood.</span>
    </div>
  </div>
</section>

<section class="summary-grid">
  <article class="stat-card"><div class="sl">Mood entries</div><div class="sv">{rated.length}</div></article>
  <article class="stat-card"><div class="sl">Avg mood</div><div class="sv">{avgMood === null ? '-' : avgMood.toFixed(1)}</div></article>
  <article class="stat-card"><div class="sl">Sleep data days</div><div class="sv">{sleepRows.length}</div></article>
  <article class="stat-card"><div class="sl">Avg sleep</div><div class="sv">{hoursMins(avgSleepMins)}</div></article>
  <article class="stat-card"><div class="sl">Avg sleep score</div><div class="sv">{avgSleepScore === null ? '-' : `${avgSleepScore.toFixed(0)}/100`}</div></article>
  <article class="stat-card"><div class="sl">Avg HRV</div><div class="sv">{avgHrv === null ? '-' : avgHrv.toFixed(0)}</div></article>
</section>

<section class="grid two">
  <article class="card">
    <h3>Mood Trend</h3>
    <svg class="chart" viewBox="0 0 640 220" preserveAspectRatio="none">
      <path class="line main" d={getSeriesPath(moodTrendValues, 640, 220)}></path>
    </svg>
    <div class="chart-meta">
      <span>Best day: {bestDay ? `${bestDay[0]} (${bestDay[1].toFixed(1)})` : '-'}</span>
      <span>Toughest day: {worstDay ? `${worstDay[0]} (${worstDay[1].toFixed(1)})` : '-'}</span>
    </div>
  </article>
  <article class="card">
    <h3>Sleep vs Mood</h3>
    <div class="mini-charts">
      <div>
        <div class="label">Sleep score vs mood</div>
        <svg class="chart" viewBox="0 0 640 160" preserveAspectRatio="none">
          <path class="line sleep" d={getSeriesPath(sleepScoreSeries, 640, 160)}></path>
          <path class="line mood" d={getSeriesPath(moodOnSleepDates, 640, 160)}></path>
        </svg>
      </div>
      <div>
        <div class="label">Sleep duration (h) vs mood</div>
        <svg class="chart" viewBox="0 0 640 160" preserveAspectRatio="none">
          <path class="line sleep" d={getSeriesPath(sleepDurationSeries, 640, 160)}></path>
          <path class="line mood" d={getSeriesPath(moodOnSleepDates, 640, 160)}></path>
        </svg>
      </div>
    </div>
  </article>
</section>

{#if mode === 'Core + one extra' && extraSection === 'Recovery Metrics'}
  <section class="grid two">
    <article class="card">
      <h3>HRV Trend</h3>
      <svg class="chart" viewBox="0 0 640 220" preserveAspectRatio="none">
        <path class="line sleep" d={getSeriesPath(hrvSeries, 640, 220)}></path>
      </svg>
    </article>
    <article class="card">
      <h3>End-of-day Body Battery Trend</h3>
      <svg class="chart" viewBox="0 0 640 220" preserveAspectRatio="none">
        <path class="line main" d={getSeriesPath(batterySeries, 640, 220)}></path>
      </svg>
    </article>
  </section>
{/if}

{#if mode === 'Core + one extra' && extraSection === 'Mood Distribution'}
  <section class="grid two">
    <article class="card">
      <h3>Mood Distribution</h3>
      {#each [1,2,3,4,5] as score, idx}
        <div class="bar-row">
          <span class="bar-label">{score}</span>
          <div class="bar-bg"><div class="bar-fill" style={`width:${Math.min(100, rated.length ? (moodCountByScore[idx] / rated.length) * 100 : 0)}%`}></div></div>
          <span class="bar-val">{moodCountByScore[idx]}</span>
        </div>
      {/each}
    </article>
    <article class="card">
      <h3>Average Mood by Hour</h3>
      <table class="table">
        <thead><tr><th>Hour</th><th>Avg mood</th></tr></thead>
        <tbody>
          {#each moodByHour as row}
            <tr><td>{row.hour}:00</td><td>{row.avg.toFixed(2)}</td></tr>
          {/each}
        </tbody>
      </table>
    </article>
  </section>
{/if}

{#if mode === 'Core + one extra' && extraSection === 'Activity Log'}
  <section class="grid two">
    <article class="card">
      <h3>Top Activities</h3>
      <table class="table">
        <thead><tr><th>Activity</th><th>Count</th><th>Avg mood when logged</th></tr></thead>
        <tbody>
          {#each activityStats as row}
            <tr>
              <td>{row.name}</td>
              <td>{row.count}</td>
              <td>{row.avgMood === null ? '-' : row.avgMood.toFixed(2)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </article>
    <article class="card">
      <h3>Selected Activity Trend</h3>
      <label>
        <div class="label">Select activity</div>
        <select bind:value={selectedActivity}>
          {#each Array.from(new Set(activities.map(a => a.name))).sort() as name}
            <option value={name}>{name}</option>
          {/each}
        </select>
      </label>
      {#if selectedActivityStats}
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Nights with selected activity</div><div class="sv">{selectedActivityStats.withCount}</div></div>
          <div class="stat-card"><div class="sl">Other nights</div><div class="sv">{selectedActivityStats.otherCount}</div></div>
        </div>
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Confidence</div><div class="sv">{selectedActivityStats.confidence}</div></div>
          <div class="stat-card"><div class="sl">Longest streak with activity</div><div class="sv">{selectedActivityStats.longestWith} days</div></div>
        </div>
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Longest streak without activity</div><div class="sv">{selectedActivityStats.longestWithout} days</div></div>
          <div class="stat-card"><div class="sl">Sleep score avg (with vs other)</div><div class="sv">{selectedActivityStats.avgScoreWith === null ? '-' : selectedActivityStats.avgScoreWith.toFixed(0)} / {selectedActivityStats.avgScoreOther === null ? '-' : selectedActivityStats.avgScoreOther.toFixed(0)}</div></div>
        </div>
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Sleep hours avg (with vs other)</div><div class="sv">{selectedActivityStats.avgTotalWith === null ? '-' : selectedActivityStats.avgTotalWith.toFixed(1)}h / {selectedActivityStats.avgTotalOther === null ? '-' : selectedActivityStats.avgTotalOther.toFixed(1)}h</div></div>
          <div class="stat-card"><div class="sl">Influence on mood (with/without)</div><div class="sv">{selectedActivityStats.withWithoutPct === null ? '-' : `${selectedActivityStats.withWithoutPct >= 0 ? '+' : ''}${selectedActivityStats.withWithoutPct.toFixed(1)}%`}</div></div>
        </div>
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Previous day effect</div><div class="sv">{selectedActivityStats.previousDayPct === null ? '-' : `${selectedActivityStats.previousDayPct >= 0 ? '+' : ''}${selectedActivityStats.previousDayPct.toFixed(1)}%`}</div></div>
          <div class="stat-card"><div class="sl">Same day effect</div><div class="sv">{selectedActivityStats.sameDayPct === null ? '-' : `${selectedActivityStats.sameDayPct >= 0 ? '+' : ''}${selectedActivityStats.sameDayPct.toFixed(1)}%`}</div></div>
        </div>
        <div class="grid two" style="margin-top:0.6rem;">
          <div class="stat-card"><div class="sl">Next day effect</div><div class="sv">{selectedActivityStats.nextDayPct === null ? '-' : `${selectedActivityStats.nextDayPct >= 0 ? '+' : ''}${selectedActivityStats.nextDayPct.toFixed(1)}%`}</div></div>
          <div class="stat-card"><div class="sl">Interpretation</div><div class="sv" style="font-size:0.95rem;line-height:1.2;">Positive % means better mood (lower mood score).</div></div>
        </div>
        <div style="margin-top:0.6rem;">
          <div class="label">Sleep score over time</div>
          <svg class="chart" viewBox="0 0 640 160" preserveAspectRatio="none">
            <path class="line main" d={getSeriesPath(selectedActivityStats.scoreWith, 640, 160)}></path>
            <path class="line sleep" d={getSeriesPath(selectedActivityStats.scoreOther, 640, 160)}></path>
          </svg>
        </div>
        <div>
          <div class="label">Sleep duration (h) over time</div>
          <svg class="chart" viewBox="0 0 640 160" preserveAspectRatio="none">
            <path class="line main" d={getSeriesPath(selectedActivityStats.totalWith, 640, 160)}></path>
            <path class="line sleep" d={getSeriesPath(selectedActivityStats.totalOther, 640, 160)}></path>
          </svg>
        </div>
        <div style="margin-top:0.6rem;">
          <div class="label">Occurrence during week</div>
          {#each ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as day, idx}
            <div class="bar-row">
              <span class="bar-label">{day}</span>
              <div class="bar-bg"><div class="bar-fill" style={`width:${Math.min(100, Math.max(...selectedActivityStats.weekdayCounts, 1) ? (selectedActivityStats.weekdayCounts[idx] / Math.max(...selectedActivityStats.weekdayCounts, 1)) * 100 : 0)}%`}></div></div>
              <span class="bar-val">{selectedActivityStats.weekdayCounts[idx]}</span>
            </div>
          {/each}
        </div>
      {/if}
    </article>
  </section>
{/if}

<style>
  .controls { display: grid; gap: 0.7rem; grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .btn-row { display:flex; align-items:end; }
  .status { margin-top: 0.5rem; color: #22543d; }
  .summary-grid { display:grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.6rem; margin-bottom: 0.7rem; }
  .stat-card { background: #fff; border: 1px solid #d9e2ef; border-radius: 12px; padding: 0.75rem; }
  .sl { color:#5f6f84; font-size:0.74rem; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; }
  .sv { color:#132238; font-size:1.45rem; font-weight:800; margin-top:0.1rem; }
  .chart { width: 100%; height: 220px; background: #f9fcff; border: 1px solid #d9e2ef; border-radius: 10px; }
  .mini-charts .chart { height: 160px; }
  .line { fill: none; stroke-width: 2.5; }
  .line.main { stroke: #1f78d1; }
  .line.sleep { stroke: #74b9ff; }
  .line.mood { stroke: #ef4444; }
  .chart-meta { display:flex; justify-content:space-between; gap:0.6rem; color:#5f6f84; font-size:0.82rem; margin-top:0.4rem; }
  .bar-row { display:grid; grid-template-columns: 28px 1fr 36px; align-items:center; gap:0.5rem; margin:0.35rem 0; }
  .bar-bg { height: 12px; background: #e8f0f9; border-radius: 999px; overflow: hidden; }
  .bar-fill { height: 100%; background: #3c79c5; }
  .bar-label, .bar-val { font-size: 0.82rem; color: #496685; }
  .legend-box { margin-top: 0.7rem; border: 1px solid #d7e6f7; border-radius: 10px; background: #f7fbff; padding: 0.55rem 0.7rem; }
  .legend-title { font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #496685; margin-bottom: 0.3rem; }
  .legend-grid { display: grid; gap: 0.2rem; color: #2a3f58; font-size: 0.82rem; }
  @media (max-width: 900px) {
    .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
</style>
