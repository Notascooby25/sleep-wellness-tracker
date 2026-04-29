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
  let date = new Date().toISOString().slice(0, 10);
  let time = new Date().toTimeString().slice(0, 5);
  let status = '';
  let busy = false;
  let latestSleep: SleepLatest | null = null;
  let latestBattery: BatteryLatest | null = null;

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
  <p>Log your mood and activity context, while keeping your existing backend API unchanged.</p>
</section>

<div class="grid two">
  <section class="card">
    <h3>New Entry</h3>
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

    {#if ratingRequired()}
      <label style="margin-top: 0.6rem; display: block;">
        <div class="label">Mood Score (1 best, 5 worst)</div>
        <input min="1" max="5" step="1" type="number" bind:value={moodScore} />
      </label>
    {:else}
      <p class="badge">Rating not required for selected activities</p>
    {/if}

    <label style="margin-top: 0.6rem; display: block;">
      <div class="label">Notes</div>
      <textarea rows="4" bind:value={notes}></textarea>
    </label>

    <div style="margin-top: 0.75rem; display: flex; gap: 0.5rem;">
      <button disabled={busy} on:click={submitEntry}>Save Entry</button>
      <button disabled={busy} on:click={load}>Refresh Data</button>
    </div>
    {#if status}<p>{status}</p>{/if}
  </section>

  <section class="card">
    <h3>Latest Garmin Snapshot</h3>
    <p><span class="badge">Sleep</span> {latestSleep?.date || '-'} | {fmtMinutes(latestSleep?.total_sleep_minutes)} | score {latestSleep?.sleep_score ?? '-'}</p>
    <p><span class="badge">Body Battery</span> {latestBattery?.date || '-'} | morning {latestBattery?.morning_value ?? '-'} | end {latestBattery?.end_of_day_value ?? '-'}</p>
  </section>
</div>

<section class="card">
  <h3>Activities</h3>
  {#if categories.length === 0}
    <p>No categories found.</p>
  {:else}
    {#each categories as category}
      <details style="margin-bottom: 0.5rem;">
        <summary>{category.name}</summary>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.3rem; margin-top: 0.4rem;">
          {#each byCategory(category.id) as activity}
            <label class="badge" style="display: flex; gap: 0.4rem; align-items: center;">
              <input
                type="checkbox"
                checked={selected.has(activity.id)}
                on:change={() => toggle(activity.id)}
              />
              {activity.name}
            </label>
          {/each}
        </div>
      </details>
    {/each}
  {/if}
</section>
