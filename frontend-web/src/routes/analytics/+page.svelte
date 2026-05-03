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
  let sleepGoalMinutes = 420;

  let selectedMood: 1 | 2 | 3 | 4 | 5 = 3;
  let selectedCategory: number | null = null;

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
  let categories: Category[] = [];
  let sleepRows: Array<Record<string, unknown>> = [];
  let bodyRows: Array<Record<string, unknown>> = [];
  let hrvRows: Array<Record<string, unknown>> = [];
  let status = '';

  let selectedActivity = '';
  let heatmapType: 'mood' | 'sleep' = 'mood';
  let heatmapMoodRows: MoodEntry[] = [];
  let heatmapSleepRows: Array<Record<string, unknown>> = [];
  
  const moodColors: Record<number, string> = {
    1: '#10b981', // green - great
    2: '#84cc16', // lime - good
    3: '#f59e0b', // amber - neutral
    4: '#ef4444', // red - struggle
    5: '#7c3aed'  // violet - crisis
  };
  
  const moodLabels: Record<number, string> = {
    1: 'Great', 2: 'Good', 3: 'Okay', 4: 'Struggling', 5: 'Crisis'
  };

  const avg = (numbers: number[]) => (numbers.length ? numbers.reduce((a, b) => a + b, 0) / numbers.length : null);
  const sum = (numbers: number[]) => numbers.reduce((a, b) => a + b, 0);
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

  const dayOffset = (isoDate: string, offsetDays: number) => {
    const d = new Date(isoDate + 'T12:00:00');
    d.setDate(d.getDate() + offsetDays);
    return d.toISOString().slice(0, 10);
  };

  const avgForDates = (dates: string[], pick: (d: string) => number | null) => {
    const vals = dates
      .map((d) => pick(d))
      .filter((n): n is number => n !== null && Number.isFinite(n));
    return avg(vals);
  };

  const heatmap84From = new Date(Date.now() - 83 * 86400000).toISOString().slice(0, 10);

  const loadHeatmap = async () => {
    try {
      const [hMood, hSleep] = await Promise.all([
        getJson<MoodEntry[]>(`/mood/?from_date=${heatmap84From}&to_date=${today}`),
        getJson<GarminRows>(`/garmin/sleep/range?start_date=${heatmap84From}&end_date=${today}`),
      ]);
      heatmapMoodRows = hMood;
      heatmapSleepRows = hSleep?.data || [];
    } catch { /* fail silently */ }
  };

  // ── Correlations & Insights Computed Properties ───────────────────────────

  $: moodCountByCategory = (() => {
    if (!selectedCategory) return [];
    const catActivities = new Set(
      activities.filter(a => a.category_id === selectedCategory).map(a => a.id)
    );
    const moodCounts: Record<number, number> = { 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 };
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const hasActivity = (e.activity_ids || []).some(id => catActivities.has(id));
      if (hasActivity) {
        moodCounts[e.mood_score as 1|2|3|4|5]++;
      }
    }
    return Object.entries(moodCounts).map(([score, count]) => ({
      score: Number(score) as 1|2|3|4|5,
      count,
      percentage: rated.length ? (count / rated.length) * 100 : 0
    }));
  })();

  $: relatedActivitiesPerMood = (() => {
    if (selectedMood === null) return [];
    const activityMoodMap = new Map<string, { count: number; times: number }>();
    let moodCount = 0;
    
    for (const e of entries) {
      if (e.mood_score === selectedMood) {
        moodCount++;
        for (const aid of e.activity_ids || []) {
          const name = activityById.get(aid)?.name || `#${aid}`;
          if (!activityMoodMap.has(name)) activityMoodMap.set(name, { count: 0, times: 0 });
          const row = activityMoodMap.get(name)!;
          row.times++;
        }
      }
    }
    
    for (const e of entries) {
      for (const aid of e.activity_ids || []) {
        const name = activityById.get(aid)?.name || `#${aid}`;
        if (activityMoodMap.has(name)) {
          activityMoodMap.get(name)!.count++;
        }
      }
    }
    
    return Array.from(activityMoodMap.entries())
      .map(([name, v]) => ({
        name,
        percentage: v.count ? (v.times / v.count) * 100 : 0,
        occurrences: v.times
      }))
      .sort((a, b) => b.percentage - a.percentage)
      .slice(0, 10);
  })();

  $: frequencyComparison = (() => {
    const mid = Math.floor(dayList.length / 2);
    const periodFirstSet = new Set(dayList.slice(0, mid));
    const periodSecondSet = new Set(dayList.slice(mid));
    
    const countFirst: Record<string, number> = {};
    const countSecond: Record<string, number> = {};
    
    for (const e of entries) {
      const d = ukDate(e.timestamp);
      if (periodFirstSet.has(d)) {
        for (const aid of e.activity_ids || []) {
          const name = activityById.get(aid)?.name || `#${aid}`;
          countFirst[name] = (countFirst[name] || 0) + 1;
        }
      }
      if (periodSecondSet.has(d)) {
        for (const aid of e.activity_ids || []) {
          const name = activityById.get(aid)?.name || `#${aid}`;
          countSecond[name] = (countSecond[name] || 0) + 1;
        }
      }
    }
    
    const allNames = new Set([...Object.keys(countFirst), ...Object.keys(countSecond)]);
    return Array.from(allNames)
      .map(name => ({
        name,
        first: countFirst[name] || 0,
        second: countSecond[name] || 0,
        trend: (countSecond[name] || 0) - (countFirst[name] || 0)
      }))
      .sort((a, b) => Math.abs(b.trend) - Math.abs(a.trend))
      .slice(0, 8);
  })();

  $: influenceMoodScores = (() => {
    const actMap = new Map<string, { with: number[]; without: number[] }>();
    
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      for (const aid of activities) {
        const name = aid.name;
        if (!actMap.has(name)) actMap.set(name, { with: [], without: [] });
        
        if ((e.activity_ids || []).includes(aid.id)) {
          actMap.get(name)!.with.push(score);
        }
      }
    }
    
    for (const e of entries) {
      if (e.mood_score === null || e.mood_score === undefined) continue;
      const score = Number(e.mood_score);
      for (const aid of activities) {
        const name = aid.name;
        if (!(e.activity_ids || []).includes(aid.id)) {
          actMap.get(name)!.without.push(score);
        }
      }
    }
    
    return Array.from(actMap.entries())
      .map(([name, v]) => ({
        name,
        influence: v.with.length && v.without.length 
          ? (avg(v.without) || 0) - (avg(v.with) || 0)
          : null,
        withCount: v.with.length,
        withoutCount: v.without.length
      }))
      .filter(x => x.withCount >= 2)
      .sort((a, b) => (Math.abs(b.influence || 0) - Math.abs(a.influence || 0)))
      .slice(0, 8);
  })();

  $: recent7Dates = dayList.slice(-7);
  $: prior7Dates = dayList.slice(-14, -7);

  $: recentSleepMinutes = recent7Dates
    .map((d) => Number(sleepByDateMap.get(d)?.total_sleep_minutes))
    .filter((n) => Number.isFinite(n));

  $: rollingSleepAvgMinutes = avg(recentSleepMinutes);
  $: sleepGoalTotalMinutes = recent7Dates.length * sleepGoalMinutes;
  $: sleepDebtMinutes = sleepGoalTotalMinutes - sum(recentSleepMinutes);

  $: weekSleepScore = avgForDates(recent7Dates, (d) => {
    const n = Number(sleepByDateMap.get(d)?.sleep_score);
    return Number.isFinite(n) ? n : null;
  });
  $: weekMood = avgForDates(recent7Dates, (d) => dailyMoodMap.get(d) ?? null);
  $: weekHrv = avgForDates(recent7Dates, (d) => {
    const n = Number(hrvByDateMap.get(d)?.weekly_avg);
    return Number.isFinite(n) ? n : null;
  });
  $: weekBodyBattery = avgForDates(recent7Dates, (d) => {
    const n = Number(bodyByDateMap.get(d)?.end_of_day_value);
    return Number.isFinite(n) ? n : null;
  });

  $: priorSleepScore = avgForDates(prior7Dates, (d) => {
    const n = Number(sleepByDateMap.get(d)?.sleep_score);
    return Number.isFinite(n) ? n : null;
  });

  $: weeklySummaryLine = (() => {
    if (weekSleepScore === null || priorSleepScore === null) {
      return 'Keep logging to unlock stronger weekly comparisons.';
    }
    const delta = weekSleepScore - priorSleepScore;
    if (delta >= 5) return 'Your sleep trend is stronger than the previous week.';
    if (delta <= -5) return 'Sleep score dipped vs last week, likely affecting recovery.';
    return 'Sleep score is broadly stable week over week.';
  })();

  onMount(() => { load(); loadHeatmap(); });

  // ── 12-week heatmap ───────────────────────────────────────────────────────
  $: heatmapDailyMood = (() => {
    const byDay = new Map<string, number[]>();
    for (const e of heatmapMoodRows) {
      if (e.mood_score == null) continue;
      const d = ukDate(e.timestamp);
      if (!byDay.has(d)) byDay.set(d, []);
      byDay.get(d)!.push(Number(e.mood_score));
    }
    const out = new Map<string, number>();
    for (const [d, arr] of byDay) out.set(d, arr.reduce((a, b) => a + b) / arr.length);
    return out;
  })();

  $: heatmapSleepScore = new Map(
    heatmapSleepRows.map(r => [String(r.date), Number(r.sleep_score)])
  );

  const heatmapCellColor = (value: number | null, type: 'mood' | 'sleep') => {
    if (value === null) return '#e2eaf4';
    if (type === 'mood') {
      const v = Math.round(value);
      if (v <= 1) return '#22c55e';
      if (v === 2) return '#84cc16';
      if (v === 3) return '#f59e0b';
      if (v === 4) return '#ef4444';
      return '#7c3aed';
    }
    if (value >= 80) return '#22c55e';
    if (value >= 65) return '#84cc16';
    if (value >= 50) return '#f59e0b';
    return '#ef4444';
  };

  const heatmapTitle = (date: string, value: number | null, type: 'mood' | 'sleep') => {
    if (value === null) return `${date}: No data`;
    if (type === 'mood') {
      const label = moodLabels[Math.round(value)] ?? value.toFixed(1);
      return `${date}: ${label} (${value.toFixed(1)})`;
    }
    return `${date}: ${value.toFixed(0)}/100`;
  };

  $: heatmapCells = (() => {
    // Align start to nearest Monday (Mon = 0)
    const startD = new Date(today + 'T12:00:00');
    startD.setDate(startD.getDate() - 83);
    const padCount = (startD.getDay() + 6) % 7; // Mon-based
    const cells: Array<{ date: string | null; value: number | null }> = [];
    for (let p = 0; p < padCount; p++) cells.push({ date: null, value: null });
    for (let i = 83; i >= 0; i--) {
      const d = new Date(today + 'T12:00:00');
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().slice(0, 10);
      let value: number | null = null;
      if (heatmapType === 'mood') {
        value = heatmapDailyMood.get(dateStr) ?? null;
      } else {
        const n = heatmapSleepScore.get(dateStr);
        value = n != null && Number.isFinite(n) ? n : null;
      }
      cells.push({ date: dateStr, value });
    }
    return cells;
  })();
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
      <div class="label">Sleep goal (minutes)</div>
      <input type="number" min="300" max="720" step="15" bind:value={sleepGoalMinutes} />
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
    <h3>Sleep vs Goal (Last 7 Days)</h3>
    <div class="week-kpis">
      <div class="stat-card"><div class="sl">Goal total</div><div class="sv">{hoursMins(sleepGoalTotalMinutes)}</div></div>
      <div class="stat-card"><div class="sl">Actual total</div><div class="sv">{hoursMins(sum(recentSleepMinutes))}</div></div>
      <div class="stat-card"><div class="sl">Avg per night</div><div class="sv">{hoursMins(rollingSleepAvgMinutes)}</div></div>
      <div class={`sleep-debt-badge ${sleepDebtMinutes > 0 ? 'debt' : 'surplus'}`}>
        {sleepDebtMinutes > 0 ? '−' : '+'}{hoursMins(Math.abs(sleepDebtMinutes))}
      </div>
    </div>
  </article>
  <article class="card">
    <h3>Week In Review</h3>
    <div class="week-kpis">
      <div class="stat-card"><div class="sl">Sleep score</div><div class="sv">{weekSleepScore === null ? '-' : `${weekSleepScore.toFixed(0)}/100`}</div></div>
      <div class="stat-card"><div class="sl">HRV</div><div class="sv">{weekHrv === null ? '-' : weekHrv.toFixed(0)}</div></div>
      <div class="stat-card"><div class="sl">Mood</div><div class="sv">{weekMood === null ? '-' : weekMood.toFixed(1)}</div></div>
      <div class="stat-card"><div class="sl">Body battery</div><div class="sv">{weekBodyBattery === null ? '-' : weekBodyBattery.toFixed(0)}</div></div>
    </div>
    <p class="week-summary">{weeklySummaryLine}</p>
  </article>
</section>

<section class="card">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:0.5rem;margin-bottom:0.75rem;">
    <h3 style="margin:0;">12-Week Heatmap</h3>
    <div class="heatmap-toggle">
      <button class:active={heatmapType === 'mood'} on:click={() => (heatmapType = 'mood')}>Mood</button>
      <button class:active={heatmapType === 'sleep'} on:click={() => (heatmapType = 'sleep')}>Sleep score</button>
    </div>
  </div>
  <div class="heatmap-wrap">
    <div class="heatmap-days">
      {#each ['M','T','W','T','F','S','S'] as d}<span>{d}</span>{/each}
    </div>
    <div class="heatmap-grid">
      {#each heatmapCells as cell}
        <div
          class="heatmap-cell"
          class:heatmap-pad={cell.date === null}
          style={cell.date !== null ? `background:${heatmapCellColor(cell.value, heatmapType)}` : ''}
          title={cell.date !== null ? heatmapTitle(cell.date, cell.value, heatmapType) : ''}
        ></div>
      {/each}
    </div>
  </div>
  <div class="heatmap-legend">
    {#if heatmapType === 'mood'}
      {#each [[1,'#22c55e','Great'],[2,'#84cc16','Good'],[3,'#f59e0b','Okay'],[4,'#ef4444','Struggling'],[5,'#7c3aed','Crisis']] as [, c, l]}
        <span class="heatmap-leg-item"><span class="heatmap-leg-swatch" style="background:{c}"></span>{l}</span>
      {/each}
    {:else}
      {#each [['80+','#22c55e'],['65–79','#84cc16'],['50–64','#f59e0b'],['< 50','#ef4444']] as [l, c]}
        <span class="heatmap-leg-item"><span class="heatmap-leg-swatch" style="background:{c}"></span>{l}</span>
      {/each}
    {/if}
    <span class="heatmap-leg-item"><span class="heatmap-leg-swatch" style="background:#e2eaf4"></span>No data</span>
  </div>
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

<section class="card">
  <h3>Correlations & Insights</h3>
  <p style="color: #5f6f84; font-size: 0.9rem; margin-bottom: 1rem;">Explore how activities, moods, and health metrics influence each other.</p>
  
  <div class="insights-grid">
      <!-- Influence on Mood -->
      <article class="insight-card">
        <h4>Influence on Mood</h4>
        <p class="insight-desc">Which activities most improve mood (lower score is better)</p>
        <div class="influence-list">
          {#each influenceMoodScores as item}
            <div class="influence-row">
              <div class="influence-bar-wrapper">
                <span class="influence-label" title="{item.name}">{item.name}</span>
                {#if item.influence !== null}
                  <div class="influence-bar" style={`
                    --influence: ${Math.max(-3, Math.min(3, item.influence))};
                    --width: ${Math.abs(Math.max(-3, Math.min(3, item.influence))) * 20}%;
                    --color: ${item.influence > 0 ? '#10b981' : '#ef4444'};
                  `}>
                    <span class="influence-val">{item.influence.toFixed(2)}</span>
                  </div>
                {:else}
                  <div class="influence-na">N/A</div>
                {/if}
              </div>
              <span class="influence-count">{item.withCount}</span>
            </div>
          {/each}
        </div>
      </article>

      <!-- Frequency Comparison -->
      <article class="insight-card">
        <h4>Frequency Comparison</h4>
        <p class="insight-desc">Activity changes: {dayList.length > 0 ? Math.floor(dayList.length / 2) : 0} days ago → now</p>
        <div class="frequency-list">
          {#each frequencyComparison as item}
            <div class="frequency-row">
              <span class="freq-label" title="{item.name}">{item.name}</span>
              <div class="freq-values">
                <span class="freq-num">{item.first}</span>
                <span class="freq-arrow" style={`color: ${item.trend > 0 ? '#10b981' : item.trend < 0 ? '#ef4444' : '#999'}`}>
                  {item.trend > 0 ? '↑' : item.trend < 0 ? '↓' : '→'}
                </span>
                <span class="freq-num">{item.second}</span>
              </div>
            </div>
          {/each}
        </div>
      </article>

      <!-- Mood Count by Category -->
      <article class="insight-card">
        <h4>Mood Count by Category</h4>
        <p class="insight-desc">Distribution of moods for selected activity category</p>
        <label style="display: block; margin-bottom: 0.6rem;">
          <div class="label">Category</div>
          <select bind:value={selectedCategory}>
            <option value={null}>All activities</option>
            {#each categories as cat}
              <option value={cat.id}>{cat.name}</option>
            {/each}
          </select>
        </label>
        <div class="mood-count-bars">
          {#each moodCountByCategory as item}
            <div class="mood-bar-row" style={`--mood-color: ${moodColors[item.score]}`}>
              <span class="mood-label">{moodLabels[item.score]}</span>
              <div class="mood-bar-bg">
                <div class="mood-bar-fill" style={`width: ${item.percentage}%`}></div>
              </div>
              <span class="mood-count">{item.count}</span>
            </div>
          {/each}
        </div>
      </article>

      <!-- Related Activities -->
      <article class="insight-card">
        <h4>Related Activities by Mood</h4>
        <p class="insight-desc">Top activities occurring with selected mood</p>
        <label style="display: block; margin-bottom: 0.6rem;">
          <div class="label">Select mood</div>
          <div class="mood-buttons">
            {#each [1,2,3,4,5] as mood}
              <button 
                class={`mood-btn ${selectedMood === mood ? 'active' : ''}`}
                style={`--mood-color: ${moodColors[mood]}`}
                on:click={() => selectedMood = mood as 1|2|3|4|5}
                title="{moodLabels[mood]}"
              >
                {mood}
              </button>
            {/each}
          </div>
        </label>
        <div class="related-activities">
          {#each relatedActivitiesPerMood as item}
            <div class="activity-row">
              <span class="activity-name" title="{item.name}">{item.name}</span>
              <div class="percentage-bar">
                <div class="percentage-fill" style={`width: ${item.percentage}%`}></div>
                <span class="percentage-text">{item.percentage.toFixed(0)}%</span>
              </div>
            </div>
          {/each}
        </div>
      </article>

      <!-- Activity-Consequence Links -->
      <article class="insight-card" style="grid-column: 1 / -1;">
        <h4>Activity-Consequence Links</h4>
        <p class="insight-desc">Visual representation of how activities link to mood consequences</p>
        <div class="consequence-grid">
          {#each influenceMoodScores.filter(x => x.influence !== null).slice(0, 6) as item}
            <div class="consequence-block">
              <div class="consequence-label">{item.name}</div>
              <div class="consequence-arrow" style={`color: ${(item.influence ?? 0) > 0 ? '#10b981' : '#ef4444'}`}>
                {(item.influence ?? 0) > 0 ? '✓' : (item.influence ?? 0) < 0 ? '✗' : '−'}
              </div>
              <div class="consequence-outcome" style={`background: ${(item.influence ?? 0) > 0 ? '#d1fae5' : '#fee2e2'}`}>
                {(item.influence ?? 0) > 0 ? 'Better Mood' : 'Lower Mood'}
              </div>
              <div class="consequence-strength">{Math.abs(item.influence || 0).toFixed(2)} pts</div>
            </div>
          {/each}
        </div>
      </article>
  </div>
</section>

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
  .week-kpis { display: grid; gap: 0.6rem; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sleep-debt-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    font-weight: 700;
    font-size: 0.92rem;
    padding: 0.6rem;
    border: 1px solid #cfe0f3;
  }
  .sleep-debt-badge.debt { color: #b42318; background: #fee4e2; border-color: #fecdca; }
  .sleep-debt-badge.surplus { color: #086c3a; background: #dcfae6; border-color: #b7e6c9; }
  .week-summary { margin: 0.75rem 0 0; color: #2a3f58; font-size: 0.9rem; }
  /* 12-week heatmap */
  .heatmap-wrap { display: flex; gap: 5px; align-items: flex-start; overflow-x: auto; padding-bottom: 2px; }
  .heatmap-days { display: grid; grid-template-rows: repeat(7, 14px); gap: 3px; }
  .heatmap-days span { font-size: 0.65rem; color: #8091a7; line-height: 14px; width: 10px; text-align: right; }
  .heatmap-grid { display: grid; grid-template-rows: repeat(7, 14px); grid-auto-flow: column; gap: 3px; }
  .heatmap-cell { width: 14px; height: 14px; border-radius: 2px; background: #e2eaf4; cursor: default; transition: opacity 0.1s; }
  .heatmap-cell:hover { opacity: 0.75; }
  .heatmap-pad { background: transparent !important; pointer-events: none; }
  .heatmap-toggle { display: flex; border: 1px solid #d9e2ef; border-radius: 8px; overflow: hidden; }
  .heatmap-toggle button { border: none; background: #f5faff; padding: 0.3rem 0.7rem; font-size: 0.82rem; cursor: pointer; color: #496685; }
  .heatmap-toggle button.active { background: #3c79c5; color: #fff; font-weight: 600; }
  .heatmap-legend { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.65rem; }
  .heatmap-leg-item { display: flex; align-items: center; gap: 0.3rem; font-size: 0.75rem; color: #496685; }
  .heatmap-leg-swatch { display: inline-block; width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; }

  /* Correlations & Insights Styles */
  .insights-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-top: 1rem; }
  .insight-card { background: #f9fcff; border: 1px solid #d9e2ef; border-radius: 12px; padding: 1rem; }
  .insight-card h4 { margin: 0 0 0.3rem 0; color: #132238; font-size: 1rem; font-weight: 700; }
  .insight-desc { margin: 0 0 0.8rem 0; color: #5f6f84; font-size: 0.85rem; }
  
  /* Influence on Mood */
  .influence-list { display: flex; flex-direction: column; gap: 0.6rem; }
  .influence-row { display: flex; gap: 0.5rem; align-items: center; }
  .influence-bar-wrapper { display: flex; align-items: center; flex: 1; gap: 0.5rem; }
  .influence-label { font-size: 0.82rem; color: #496685; flex: 0 0 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .influence-bar { flex: 1; height: 24px; background: #e8f0f9; border-radius: 6px; display: flex; align-items: center; justify-content: center; border-left: 3px solid var(--color); }
  .influence-val { font-size: 0.75rem; font-weight: 600; color: #132238; }
  .influence-na { padding: 0 0.5rem; font-size: 0.75rem; color: #999; }
  .influence-count { font-size: 0.82rem; color: #999; flex: 0 0 40px; text-align: right; }

  /* Frequency Comparison */
  .frequency-list { display: flex; flex-direction: column; gap: 0.5rem; }
  .frequency-row { display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: #fff; border-radius: 8px; border: 1px solid #e0e7ff; }
  .freq-label { font-size: 0.82rem; color: #496685; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .freq-values { display: flex; gap: 0.5rem; align-items: center; }
  .freq-num { font-size: 0.82rem; font-weight: 600; color: #132238; flex: 0 0 30px; text-align: center; }
  .freq-arrow { font-size: 1rem; flex: 0 0 20px; text-align: center; }

  /* Mood Count by Category */
  .mood-count-bars { display: flex; flex-direction: column; gap: 0.5rem; }
  .mood-bar-row { display: grid; grid-template-columns: 60px 1fr 40px; align-items: center; gap: 0.5rem; }
  .mood-label { font-size: 0.82rem; color: #496685; }
  .mood-bar-bg { height: 20px; background: #e8f0f9; border-radius: 6px; overflow: hidden; }
  .mood-bar-fill { height: 100%; background: var(--mood-color); transition: width 0.3s ease; }
  .mood-count { font-size: 0.82rem; font-weight: 600; color: #132238; }

  /* Mood Buttons */
  .mood-buttons { display: flex; gap: 0.5rem; }
  .mood-btn { padding: 0.5rem 0.75rem; border: 2px solid #d9e2ef; border-radius: 8px; background: #fff; color: #132238; font-weight: 600; cursor: pointer; transition: all 0.2s ease; font-size: 0.9rem; }
  .mood-btn:hover { border-color: var(--mood-color); }
  .mood-btn.active { border-color: var(--mood-color); background: var(--mood-color); color: #fff; }

  /* Related Activities */
  .related-activities { display: flex; flex-direction: column; gap: 0.5rem; }
  .activity-row { display: flex; gap: 0.5rem; align-items: center; }
  .activity-name { font-size: 0.82rem; color: #496685; flex: 0 0 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .percentage-bar { flex: 1; height: 22px; background: #e8f0f9; border-radius: 6px; position: relative; overflow: hidden; }
  .percentage-fill { height: 100%; background: linear-gradient(90deg, #3c79c5, #74b9ff); }
  .percentage-text { position: absolute; top: 50%; left: 0.5rem; transform: translateY(-50%); font-size: 0.75rem; font-weight: 600; color: #132238; }

  /* Activity-Consequence Links */
  .consequence-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.8rem; margin-top: 0.8rem; }
  .consequence-block { display: flex; flex-direction: column; align-items: center; padding: 0.8rem; background: #fff; border: 1px solid #d9e2ef; border-radius: 10px; }
  .consequence-label { font-size: 0.75rem; color: #496685; text-align: center; margin-bottom: 0.4rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; width: 100%; }
  .consequence-arrow { font-size: 1.5rem; margin: 0.3rem 0; }
  .consequence-outcome { padding: 0.4rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; color: #132238; text-align: center; margin: 0.3rem 0; }
  .consequence-strength { font-size: 0.8rem; color: #5f6f84; font-weight: 600; }

  @media (max-width: 900px) {
    .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .insights-grid { grid-template-columns: 1fr; }
    .consequence-grid { grid-template-columns: repeat(3, 1fr); }
    .week-kpis { grid-template-columns: 1fr; }
  }

  @media (max-width: 600px) {
    .insights-grid { grid-template-columns: 1fr; }
    .consequence-grid { grid-template-columns: 1fr; }
    .summary-grid { grid-template-columns: 1fr; }
  }
</style>
