<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, postJson } from '$lib/api';
  import type { Activity, Category, GarminLatestWrap, MoodEntry } from '$lib/types';

  type SleepLatest = {
    date: string;
    total_sleep_minutes?: number;
    sleep_score?: number;
  };

  type BatteryLatest = {
    date: string;
    morning_value?: number;
    end_of_day_value?: number;
  };

  let categories: Category[] = [];
  let activities: Activity[] = [];
  let selected = new Set<number>();
  let notes = '';
  let moodScore = 3;
<<<<<<< HEAD
  // Derive both date and time from the same local instant to avoid UTC/local mismatch.
  const now = new Date();
  const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString();
  let date = localIso.slice(0, 10);
  let time = localIso.slice(11, 16);
=======
  let date = new Date().toISOString().slice(0, 10);
  let time = new Date().toTimeString().slice(0, 5);
>>>>>>> feat/new-frontend-sveltekit
  let status = '';
  let busy = false;
  let latestSleep: SleepLatest | null = null;
  let latestBattery: BatteryLatest | null = null;
  let activeCategory = 0;

  const fmtMinutes = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${Math.floor(value / 60)}h ${String(value % 60).padStart(2, '0')}m`;
  };

  const byCategory = (catId: number) => activities.filter((a) => a.category_id === catId);

  const ratingRequired = () => {
    for (const id of selected) {
      const act = activities.find((a) => a.id === id);
      if (!act) continue;
      const cat = categories.find((c) => c.id === act.category_id);
      if (!cat) continue;
      if ((cat.require_rating ?? 1) === 1) return true;
    }
    return selected.size === 0;
  };

  const toggle = (id: number) => {
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    selected = new Set(selected);
  };

  const clearSelected = () => {
    selected = new Set<number>();
  };

  const moodColors: Record<number, { bg: string; active: string }> = {
    1: { bg: '#bbf7d0', active: '#16a34a' },
    2: { bg: '#d9f99d', active: '#65a30d' },
    3: { bg: '#fef08a', active: '#ca8a04' },
    4: { bg: '#fed7aa', active: '#ea580c' },
    5: { bg: '#fecaca', active: '#dc2626' },
  };

  const load = async () => {
    try {
      const [cats, acts, sleepWrap, batteryWrap] = await Promise.all([
        getJson<Category[]>('/categories/'),
        getJson<Activity[]>('/activities/'),
        getJson<GarminLatestWrap<SleepLatest>>('/garmin/sleep/latest'),
        getJson<GarminLatestWrap<BatteryLatest>>('/garmin/body-battery/latest')
      ]);
      categories = cats;
      activities = acts;
      latestSleep = sleepWrap?.data || null;
      latestBattery = batteryWrap?.data || null;
    } catch (error) {
      status = `Load error: ${error}`;
    }
  };

  const submitEntry = async () => {
    busy = true;
    status = '';
    try {
      const timestamp = new Date(`${date}T${time}:00`).toISOString();
      const payload: MoodEntry = {
        mood_score: ratingRequired() ? moodScore : null,
        notes: notes.trim() || null,
        timestamp,
        activity_ids: Array.from(selected)
      };
      await postJson('/mood/', payload);
      status = 'Entry saved.';
      notes = '';
      selected = new Set<number>();
    } catch (error) {
      status = `Save failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Mood Entry</h2>
  <p>Log your mood and activity context.</p>
</section>

{#if latestSleep || latestBattery}
<section class="card garmin-snap">
  <span class="snap-label">Last night</span>
  {#if latestSleep}
    <span class="snap-pill">Sleep {fmtMinutes(latestSleep.total_sleep_minutes)} · score {latestSleep.sleep_score ?? '-'}/100</span>
  {/if}
  {#if latestBattery}
    <span class="snap-pill">Body battery AM {latestBattery.morning_value ?? '-'} · EOD {latestBattery.end_of_day_value ?? '-'}</span>
  {/if}
</section>
{/if}

<section class="card">
  <div class="grid two">
    <label>
      <div class="label">Date</div>
      <input type="date" bind:value={date} />
    </label>
    <label>
      <div class="label">Time</div>
      <input type="time" bind:value={time} />
    </label>
  </div>

  <div style="margin-top:0.8rem;">
    <div class="label">Mood Score <small style="color:#8091a7;">(1 = great, 5 = struggling)</small></div>
    {#if ratingRequired()}
      <div class="mood-pills">
        {#each [1,2,3,4,5] as score}
          <button
            class="mood-pill"
            class:mood-pill-active={moodScore === score}
            style="--pill-bg:{moodColors[score].bg};--pill-active:{moodColors[score].active};"
            on:click={() => (moodScore = score)}
          >{score}{moodScore === score ? ' ✓' : ''}</button>
        {/each}
      </div>
      <p class="label" style="margin-top:0.3rem;">Selected mood score: {moodScore}</p>
    {:else}
      <p class="badge-info">Rating not required for selected activities</p>
    {/if}
  </div>

  <label style="margin-top: 0.8rem; display: block;">
    <div class="label">Notes</div>
    <textarea rows="3" bind:value={notes}></textarea>
  </label>

  <div style="margin-top: 0.75rem; display: flex; gap: 0.5rem;">
    <button class="btn-primary" disabled={busy} on:click={submitEntry}>Save Entry</button>
    <button disabled={busy} on:click={load}>Refresh</button>
  </div>
  {#if status}<p class="status-msg">{status}</p>{/if}
</section>

<section class="card">
  <div class="acts-header">
    <h3 style="margin:0;">Activities</h3>
    <span class="label" style="flex:1;margin:0;">Tap chips to toggle, then switch categories using tabs.</span>
    <button class="btn-clear" on:click={clearSelected}>Clear</button>
  </div>

  {#if selected.size > 0}
    <div class="selected-summary">
      {#each Array.from(selected) as id}
        {@const act = activities.find(a => a.id === id)}
        {#if act}
          <button class="chip chip-selected" on:click={() => toggle(id)}>{act.name} ×</button>
        {/if}
      {/each}
    </div>
  {/if}

  {#if categories.length === 0}
    <p>No categories found.</p>
  {:else}
    <div class="cat-tabs">
      {#each categories as cat, i}
        <button
          class="cat-tab"
          class:cat-tab-active={activeCategory === i}
          on:click={() => (activeCategory = i)}
        >
          {cat.name}
          {#if byCategory(cat.id).some(a => selected.has(a.id))}
            <span class="cat-dot"></span>
          {/if}
        </button>
      {/each}
    </div>

    {#if categories[activeCategory]}
      {@const catActivities = byCategory(categories[activeCategory].id)}
      <div class="chips">
        {#each catActivities as activity}
          <button
            class="chip"
            class:chip-selected={selected.has(activity.id)}
            on:click={() => toggle(activity.id)}
          >{activity.name}</button>
        {:else}
          <p class="label">No activities in this category.</p>
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .garmin-snap { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .snap-label { font-size: 0.78rem; font-weight: 700; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; }
  .snap-pill { background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.18rem 0.55rem; font-size: 0.8rem; color: #1e4b76; }
  .mood-pills { display: flex; gap: 0.5rem; margin-top: 0.35rem; flex-wrap: wrap; }
  .mood-pill {
    flex: 1 1 0; min-width: 52px; max-width: 100px;
    padding: 0.6rem 0; border-radius: 999px; border: 2px solid transparent;
    background: var(--pill-bg); color: #132238;
    font-size: 1rem; font-weight: 700; cursor: pointer; transition: all 0.12s;
  }
  .mood-pill-active {
    background: var(--pill-active) !important; border-color: var(--pill-active) !important;
    color: #fff !important; box-shadow: 0 0 0 3px rgba(0,0,0,0.08);
  }
  .badge-info { font-size: 0.84rem; color: #496685; background: #eef4fb; border: 1px solid #ccddf4; border-radius: 8px; padding: 0.35rem 0.6rem; margin-top: 0.35rem; }
  .btn-primary { background: #3c79c5; color: #fff; border-color: #3168ad; }
  .btn-clear { background: transparent; border-color: #c7d9ef; color: #496685; font-size: 0.84rem; padding: 0.3rem 0.7rem; white-space: nowrap; }
  .status-msg { font-size: 0.88rem; color: #22543d; background: #d4edda; border-radius: 8px; padding: 0.3rem 0.6rem; margin-top: 0.4rem; }
  .acts-header { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.55rem; }
  .selected-summary { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e8f0f9; }
  .cat-tabs { display: flex; flex-wrap: wrap; gap: 0.3rem; border-bottom: 2px solid #e2eaf4; margin-bottom: 0.6rem; padding-bottom: 0.35rem; }
  .cat-tab { position: relative; background: transparent; border: 1px solid #d7e6f7; border-radius: 999px; padding: 0.3rem 0.65rem; font-size: 0.82rem; color: #1e4b76; cursor: pointer; }
  .cat-tab-active { background: #d4e9ff; border-color: #a9c9ea; font-weight: 700; }
  .cat-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #3c79c5; margin-left: 4px; vertical-align: middle; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.3rem; }
  .chip { background: #ecf2fb; border: 1px solid #ccddf4; color: #1f4066; border-radius: 999px; padding: 0.3rem 0.75rem; font-size: 0.84rem; cursor: pointer; transition: all 0.1s; }
  .chip-selected { background: #3c79c5; border-color: #3168ad; color: #fff; }
</style>
