<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, postJson } from '$lib/api';

  type MetricRow = Record<string, unknown>;
  type WrappedRows = { data: MetricRow[] };

  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  let startDate = thirtyDaysAgo;
  let endDate = today;
  let status = '';
  let busy = false;

  // Sync settings
  let syncScope = 'smart';
  let backfillDays = 30;
  let forceSync = false;
  let showEmptyDays = false;

  const syncScopeOptions = [
    { value: 'smart', label: 'Smart (windowed)' },
    { value: 'all', label: 'All metrics' },
    { value: 'sleep', label: 'Sleep only' },
    { value: 'body', label: 'Body Battery only' },
    { value: 'hrv', label: 'HRV only' },
    { value: 'rhr', label: 'Resting HR only' },
    { value: 'stress', label: 'Stress only' },
    { value: 'hydration', label: 'Hydration only' },
  ];

  let sleepByDate: Record<string, MetricRow> = {};
  let bodyByDate: Record<string, MetricRow> = {};
  let hrvByDate: Record<string, MetricRow> = {};
  let rhrByDate: Record<string, MetricRow> = {};
  let stressByDate: Record<string, MetricRow> = {};
  let hydrationByDate: Record<string, MetricRow> = {};

  const toByDate = (rows: MetricRow[], dateKey: string): Record<string, MetricRow> =>
    Object.fromEntries(rows.filter(r => r[dateKey]).map(r => [String(r[dateKey]), r]));

  const fmt = (v: unknown, unit = '') => (v === null || v === undefined ? '-' : `${v}${unit}`);
  const fmtMinutes = (v: unknown) => {
    if (v === null || v === undefined) return '-';
    const total = Number(v);
    return `${Math.floor(total / 60)}h ${String(total % 60).padStart(2, '0')}m`;
  };
  const fmtMl = (v: unknown) => {
    if (v === null || v === undefined) return '-';
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    return `${n} ml`;
  };

  const load = async () => {
    status = '';
    try {
      const [sleepWrap, bodyWrap, hrvWrap, rhrWrap, stressWrap, hydWrap] = await Promise.all([
        getJson<WrappedRows>(`/garmin/sleep/range?start_date=${startDate}&end_date=${endDate}`),
        getJson<WrappedRows>(`/garmin/body-battery/range?start_date=${startDate}&end_date=${endDate}`),
        getJson<WrappedRows>(`/garmin/hrv/range?start_date=${startDate}&end_date=${endDate}`),
        getJson<WrappedRows>(`/garmin/resting-heart-rate/range?start_date=${startDate}&end_date=${endDate}`),
        getJson<WrappedRows>(`/garmin/stress/range?start_date=${startDate}&end_date=${endDate}`),
        getJson<WrappedRows>(`/garmin/hydration/range?start_date=${startDate}&end_date=${endDate}`),
      ]);
      sleepByDate = toByDate(sleepWrap?.data || [], 'date');
      bodyByDate = toByDate(bodyWrap?.data || [], 'date');
      hrvByDate = toByDate(hrvWrap?.data || [], 'date');
      rhrByDate = toByDate(rhrWrap?.data || [], 'date');
      stressByDate = toByDate(stressWrap?.data || [], 'date');
      hydrationByDate = toByDate(hydWrap?.data || [], 'date');
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  const syncNow = async () => {
    busy = true;
    status = 'Syncing…';
    try {
      const params = new URLSearchParams({
        mode: syncScope,
        force: forceSync ? 'true' : 'false',
        backfill_days: String(backfillDays),
      });
      await postJson(`/garmin/sync-now?${params}`, {});
      status = 'Sync complete. Refreshing…';
      await load();
      status = 'Synced successfully.';
    } catch (error) {
      status = `Sync failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  $: allDates = (() => {
    const s = new Set<string>([
      ...Object.keys(sleepByDate),
      ...Object.keys(bodyByDate),
      ...Object.keys(hrvByDate),
      ...Object.keys(rhrByDate),
      ...Object.keys(stressByDate),
      ...Object.keys(hydrationByDate),
    ]);
    return [...s].sort().reverse();
  })();

  $: counts = {
    sleep: Object.keys(sleepByDate).length,
    body: Object.keys(bodyByDate).length,
    hrv: Object.keys(hrvByDate).length,
    rhr: Object.keys(rhrByDate).length,
    stress: Object.keys(stressByDate).length,
    hydration: Object.keys(hydrationByDate).length,
  };

  const fmtDay = (dateStr: string) => {
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Garmin Log</h2>
  <p>Daily Garmin recovery and wellness summaries. Sleep and body battery stay visible on the mood pages; this page is for the wider Garmin view.</p>
</section>

<section class="card">
  <div class="controls-row">
    <label style="flex:1 1 140px">
      <div class="label">Start date</div>
      <input type="date" bind:value={startDate} />
    </label>
    <label style="flex:1 1 140px">
      <div class="label">End date</div>
      <input type="date" bind:value={endDate} />
    </label>
    <div style="display:flex;align-items:flex-end;gap:0.4rem;flex-shrink:0;">
      <button on:click={load}>Refresh</button>
      <button class="btn-sync" disabled={busy} on:click={syncNow}>
        {busy ? 'Syncing…' : 'Sync Garmin'}
      </button>
    </div>
  </div>

  <details class="sync-panel">
    <summary>Sync settings</summary>
    <div class="sync-grid">
      <label style="flex:2 1 200px">
        <div class="label">
          Sync scope
          <span class="help-icon" title="Single-metric sync is usually more reliable for larger backfills.">?</span>
        </div>
        <select bind:value={syncScope}>
          {#each syncScopeOptions as opt}
            <option value={opt.value}>{opt.label}</option>
          {/each}
        </select>
      </label>
      <label style="flex:1 1 140px">
        <div class="label">
          Backfill days
          <span class="help-icon" title="Overrides env backfill days for this sync request only.">?</span>
        </div>
        <div class="num-wrap">
          <button class="num-btn" on:click={() => (backfillDays = Math.max(1, backfillDays - 1))}>−</button>
          <input class="num-input" type="number" min="1" max="730" bind:value={backfillDays} />
          <button class="num-btn" on:click={() => (backfillDays = Math.min(730, backfillDays + 1))}>+</button>
        </div>
      </label>
    </div>
    <div class="sync-checks">
      <label class="chk"><input type="checkbox" bind:checked={forceSync} /> Force sync</label>
      <label class="chk"><input type="checkbox" bind:checked={showEmptyDays} /> Show empty days</label>
    </div>
  </details>

  {#if status}<p class="status-msg">{status}</p>{/if}
</section>

<div class="summary-grid">
  {#each [['SLEEP DAYS', counts.sleep], ['BODY BATTERY DAYS', counts.body], ['HRV DAYS', counts.hrv], ['RESTING HR DAYS', counts.rhr], ['STRESS DAYS', counts.stress], ['HYDRATION DAYS', counts.hydration]] as [label, count]}
    <div class="summary-card">
      <div class="sum-label">{label}</div>
      <div class="sum-value">{count}</div>
    </div>
  {/each}
</div>

{#if allDates.length === 0}
  <section class="card"><p>No Garmin data found for this date range.</p></section>
{:else}
  {#each allDates as dateStr, idx}
    {@const sleep = sleepByDate[dateStr]}
    {@const body = bodyByDate[dateStr]}
    {@const hrv = hrvByDate[dateStr]}
    {@const rhr = rhrByDate[dateStr]}
    {@const stress = stressByDate[dateStr]}
    {@const hydration = hydrationByDate[dateStr]}
    {@const hasAny = !!(sleep || body || hrv || rhr || stress || hydration)}
    {#if hasAny || showEmptyDays}
      <details class="day-card" open={idx === 0}>
        <summary class="day-summary">
          <span class="day-title">{fmtDay(dateStr)}</span>
          <span class="day-pills">
            {#if sleep?.sleep_score != null}<span class="mpill">Sleep score {sleep.sleep_score}/100</span>{/if}
            {#if body?.end_of_day_value != null}<span class="mpill">Body battery {body.end_of_day_value}</span>{/if}
            {#if hrv?.weekly_avg != null}<span class="mpill">HRV {hrv.weekly_avg}</span>{/if}
            {#if rhr?.resting_heart_rate != null}<span class="mpill">Resting HR {rhr.resting_heart_rate}</span>{/if}
          </span>
        </summary>
        <div class="day-metrics">
          <div class="mc">
            <div class="mc-name">Sleep</div>
            {#if sleep}
              <div class="mr"><span>Total</span><span>{fmtMinutes(sleep.total_sleep_minutes)}</span></div>
              <div class="mr"><span>Deep</span><span>{fmtMinutes(sleep.deep_sleep_minutes)}</span></div>
              <div class="mr"><span>REM</span><span>{fmtMinutes(sleep.rem_sleep_minutes)}</span></div>
              <div class="mr"><span>Light</span><span>{fmtMinutes(sleep.light_sleep_minutes)}</span></div>
              <div class="mr"><span>Score</span><span>{fmt(sleep.sleep_score, '/100')}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
          <div class="mc">
            <div class="mc-name">Body Battery</div>
            {#if body}
              <div class="mr"><span>Morning</span><span>{fmt(body.morning_value)}</span></div>
              <div class="mr"><span>End of day</span><span>{fmt(body.end_of_day_value)}</span></div>
              <div class="mr"><span>Peak</span><span>{fmt(body.peak_value)}</span></div>
              <div class="mr"><span>Low</span><span>{fmt(body.low_value)}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
          <div class="mc">
            <div class="mc-name">HRV</div>
            {#if hrv}
              <div class="mr"><span>Weekly avg</span><span>{fmt(hrv.weekly_avg)}</span></div>
              <div class="mr"><span>Baseline low</span><span>{fmt(hrv.baseline_low)}</span></div>
              <div class="mr"><span>Baseline high</span><span>{fmt(hrv.baseline_high)}</span></div>
              <div class="mr"><span>Status</span><span>{fmt(hrv.status)}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
          <div class="mc">
            <div class="mc-name">Resting HR</div>
            {#if rhr}
              <div class="mr"><span>Resting</span><span>{fmt(rhr.resting_heart_rate, ' bpm')}</span></div>
              <div class="mr"><span>Min</span><span>{fmt(rhr.min_heart_rate, ' bpm')}</span></div>
              <div class="mr"><span>Max</span><span>{fmt(rhr.max_heart_rate, ' bpm')}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
          <div class="mc">
            <div class="mc-name">Stress</div>
            {#if stress}
              <div class="mr"><span>Overall</span><span>{fmt(stress.overall_stress_level)}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
          <div class="mc">
            <div class="mc-name">Hydration</div>
            {#if hydration}
              <div class="mr"><span>Consumed</span><span>{fmtMl(hydration.consumed_ml)}</span></div>
              <div class="mr"><span>Goal</span><span>{fmtMl(hydration.goal_ml)}</span></div>
              <div class="mr"><span>Goal achieved</span><span>{hydration.goal_ml != null && hydration.consumed_ml != null && Number(hydration.consumed_ml) >= Number(hydration.goal_ml) ? '✓' : '-'}</span></div>
            {:else}<p class="no-data">No data</p>{/if}
          </div>
        </div>
      </details>
    {/if}
  {/each}
{/if}

<style>
  .controls-row { display: flex; gap: 0.75rem; align-items: flex-end; flex-wrap: wrap; }
  .btn-sync { background: #ef4444; color: #fff; border-color: #dc2626; font-weight: 700; }
  .sync-panel { margin-top: 0.75rem; border: 1px solid #d7e6f7; border-radius: 10px; padding: 0.5rem 0.75rem; background: #f8fbff; }
  .sync-panel summary { cursor: pointer; font-weight: 600; color: #1e4b76; list-style: none; user-select: none; }
  .sync-grid { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.75rem; }
  .num-wrap { display: flex; align-items: center; border: 1px solid #c7d9ef; border-radius: 10px; overflow: hidden; }
  .num-input { border: none; border-radius: 0; text-align: center; width: 60px; }
  .num-btn { border: none; border-radius: 0; background: #edf4fd; padding: 0.45rem 0.6rem; cursor: pointer; }
  .sync-checks { display: flex; gap: 1.5rem; margin-top: 0.6rem; }
  .chk { display: flex; align-items: center; gap: 0.35rem; font-size: 0.9rem; cursor: pointer; }
  .chk input { width: auto; }
  .help-icon { display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: 50%; background: #d7e6f7; color: #496685; font-size: 0.68rem; font-weight: 700; cursor: help; margin-left: 2px; }
  .status-msg { font-size: 0.88rem; background: #d4edda; color: #22543d; border-radius: 8px; padding: 0.3rem 0.6rem; margin-top: 0.5rem; }
  .summary-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 0.6rem; margin-bottom: 0.75rem; }
  @media (max-width: 700px) { .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .summary-card { background: #fff; border: 1px solid #d9e2ef; border-radius: 12px; padding: 0.75rem; }
  .sum-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: #496685; }
  .sum-value { font-size: 1.6rem; font-weight: 800; color: #132238; margin-top: 0.15rem; }
  .day-card { background: #fff; border: 1px solid #d9e2ef; border-radius: 12px; margin-bottom: 8px; overflow: hidden; }
  .day-summary { cursor: pointer; padding: 0.65rem 0.9rem; display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; user-select: none; list-style: none; }
  .day-title { font-size: 1rem; font-weight: 700; color: #132238; flex-shrink: 0; }
  .day-pills { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .mpill { background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.15rem 0.5rem; font-size: 0.74rem; font-weight: 700; color: #1e4b76; }
  .day-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; border-top: 1px solid #e8f0f9; padding: 0.6rem 0.9rem; }
  @media (max-width: 600px) { .day-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .mc { background: #f8fbff; border: 1px solid #e2eaf4; border-radius: 8px; padding: 0.5rem 0.65rem; }
  .mc-name { font-size: 0.78rem; font-weight: 700; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.35rem; }
  .mr { display: flex; justify-content: space-between; font-size: 0.82rem; color: #132238; padding: 0.08rem 0; }
  .mr span:first-child { color: #496685; }
  .no-data { font-size: 0.82rem; color: #8091a7; margin: 0; }
</style>
