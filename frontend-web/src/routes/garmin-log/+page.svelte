<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, postJson } from '$lib/api';

  type WrappedRows = { data: Record<string, unknown>[] };

  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  let startDate = thirtyDaysAgo;
  let endDate = today;
  let status = '';
  let busy = false;

  let counts: Record<string, number> = {
    sleep: 0,
    'body-battery': 0,
    hrv: 0,
    'resting-heart-rate': 0,
    stress: 0,
    hydration: 0
  };

  const metricPaths = Object.keys(counts);

  const load = async () => {
    status = '';
    try {
      const results = await Promise.all(
        metricPaths.map(async (metric) => {
          const row = await getJson<WrappedRows>(`/garmin/${metric}/range?start_date=${startDate}&end_date=${endDate}`);
          return [metric, (row?.data || []).length] as const;
        })
      );
      counts = Object.fromEntries(results);
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  const syncNow = async (mode: string) => {
    busy = true;
    status = '';
    try {
      await postJson(`/garmin/sync-now?mode=${mode}`, {});
      status = `Sync started: ${mode}`;
      await load();
    } catch (error) {
      status = `Sync failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Garmin Log</h2>
  <p>Sync Garmin data and inspect how much data is available by metric and date range.</p>
</section>

<section class="card">
  <div class="grid three">
    <label>
      <div class="label">Start date</div>
      <input type="date" bind:value={startDate} />
    </label>
    <label>
      <div class="label">End date</div>
      <input type="date" bind:value={endDate} />
    </label>
    <div style="display:flex; align-items:end;">
      <button on:click={load}>Refresh Range</button>
    </div>
  </div>
</section>

<section class="card">
  <h3>Manual Sync</h3>
  <div style="display:flex; flex-wrap:wrap; gap:0.4rem;">
    <button on:click={() => syncNow('smart')} disabled={busy}>Smart</button>
    <button on:click={() => syncNow('sleep')} disabled={busy}>Sleep</button>
    <button on:click={() => syncNow('body')} disabled={busy}>Body Battery</button>
    <button on:click={() => syncNow('hrv')} disabled={busy}>HRV</button>
    <button on:click={() => syncNow('rhr')} disabled={busy}>Resting HR</button>
    <button on:click={() => syncNow('stress')} disabled={busy}>Stress</button>
    <button on:click={() => syncNow('hydration')} disabled={busy}>Hydration</button>
    <button on:click={() => syncNow('all')} disabled={busy}>All</button>
  </div>
  {#if status}<p>{status}</p>{/if}
</section>

<section class="card">
  <h3>Range Summary</h3>
  <div class="grid three">
    {#each Object.entries(counts) as [metric, count]}
      <div class="card" style="margin:0;">
        <strong>{metric}</strong>
        <p style="margin:0.25rem 0 0;">{count} days</p>
      </div>
    {/each}
  </div>
</section>
