<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';
  import type { MoodEntry } from '$lib/types';

  type GarminRows = { data: Array<Record<string, unknown>> };

  const today = new Date().toISOString().slice(0, 10);
  const monthAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  let fromDate = monthAgo;
  let toDate = today;
  let entries: MoodEntry[] = [];
  let sleepRows: Array<Record<string, unknown>> = [];
  let status = '';

  const avg = (numbers: number[]) => (numbers.length ? numbers.reduce((a, b) => a + b, 0) / numbers.length : null);

  const load = async () => {
    status = '';
    try {
      const [moodData, sleepWrap] = await Promise.all([
        getJson<MoodEntry[]>(`/mood/?from_date=${fromDate}&to_date=${toDate}`),
        getJson<GarminRows>(`/garmin/sleep/range?start_date=${fromDate}&end_date=${toDate}`)
      ]);
      entries = moodData;
      sleepRows = sleepWrap?.data || [];
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  $: rated = entries.filter((e) => e.mood_score !== null).map((e) => Number(e.mood_score));
  $: sleepScores = sleepRows
    .map((r) => Number(r.sleep_score))
    .filter((n) => Number.isFinite(n));
  $: avgMood = avg(rated);
  $: avgSleepScore = avg(sleepScores);

  onMount(load);
</script>

<section class="hero">
  <h2>Analytics</h2>
  <p>Core trend summaries for mood and sleep, using the same backend routes as Streamlit.</p>
</section>

<section class="card">
  <div class="grid three">
    <label>
      <div class="label">From</div>
      <input type="date" bind:value={fromDate} />
    </label>
    <label>
      <div class="label">To</div>
      <input type="date" bind:value={toDate} />
    </label>
    <div style="display:flex; align-items:end;">
      <button on:click={load}>Refresh</button>
    </div>
  </div>
</section>

<section class="grid three">
  <article class="card">
    <div class="label">Mood Entries</div>
    <h3>{entries.length}</h3>
  </article>
  <article class="card">
    <div class="label">Avg Mood (1 best)</div>
    <h3>{avgMood === null ? '-' : avgMood.toFixed(2)}</h3>
  </article>
  <article class="card">
    <div class="label">Avg Sleep Score</div>
    <h3>{avgSleepScore === null ? '-' : avgSleepScore.toFixed(1)}</h3>
  </article>
</section>

<section class="card">
  <h3>Recent Mood Entries</h3>
  {#if entries.length === 0}
    <p>No data in selected range.</p>
  {:else}
    <table class="table">
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Mood</th>
          <th>Activities</th>
          <th>Notes</th>
        </tr>
      </thead>
      <tbody>
        {#each entries.slice(0, 30) as entry}
          <tr>
            <td>{new Date(entry.timestamp).toLocaleString('en-GB', { hour12: false })}</td>
            <td>{entry.mood_score ?? 'n/a'}</td>
            <td>{entry.activity_ids?.length || 0}</td>
            <td>{entry.notes || '-'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}

  {#if status}
    <p>{status}</p>
  {/if}
</section>
