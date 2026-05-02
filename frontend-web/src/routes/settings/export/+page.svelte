<script lang="ts">
  import { onMount } from 'svelte';

  import { getJson } from '$lib/api';

  type Category = { id: number; name: string };
  type Activity = { id: number; name: string; category_id?: number | null };

  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  const sourceOptions = [
    { value: 'sleep', label: 'Sleep' },
    { value: 'hrv', label: 'HRV' },
    { value: 'stress', label: 'Stress' },
    { value: 'body_battery', label: 'Body Battery' },
    { value: 'rhr', label: 'Resting Heart Rate' },
    { value: 'hydration', label: 'Hydration' },
    { value: 'steps', label: 'Steps' },
    { value: 'mood', label: 'Mood Log' },
    { value: 'activities', label: 'Garmin Activities' }
  ];

  let startDate = thirtyDaysAgo;
  let endDate = today;
  let selected = new Set<string>(['sleep', 'hrv', 'stress', 'body_battery', 'steps']);
  let categories: Category[] = [];
  let activities: Activity[] = [];
  let selectedActivityIds = new Set<number>();
  let busy = false;
  let status = '';

  const loadCatalog = async () => {
    try {
      const [categoryRows, activityRows] = await Promise.all([
        getJson<Category[]>('/categories'),
        getJson<Activity[]>('/activities')
      ]);
      categories = (categoryRows || []).slice().sort((a, b) => a.name.localeCompare(b.name));
      activities = (activityRows || []).slice().sort((a, b) => a.name.localeCompare(b.name));
    } catch (error) {
      status = `Could not load activity catalog: ${error}`;
    }
  };

  const toggleSource = (value: string) => {
    if (selected.has(value)) {
      selected.delete(value);
    } else {
      selected.add(value);
    }
    selected = new Set(selected);
  };

  const toggleActivity = (activityId: number) => {
    if (selectedActivityIds.has(activityId)) {
      selectedActivityIds.delete(activityId);
    } else {
      selectedActivityIds.add(activityId);
    }
    selectedActivityIds = new Set(selectedActivityIds);
  };

  const clearActivities = () => {
    selectedActivityIds = new Set<number>();
  };

  const selectAllActivities = () => {
    selectedActivityIds = new Set(activities.map((activity) => activity.id));
  };

  let activeCategory = 0;

  const byCategory = (catId: number) => activities.filter((a) => a.category_id === catId);

  const exportCsv = async () => {
    status = '';
    if (!startDate || !endDate) {
      status = 'Please choose both start and end dates.';
      return;
    }
    if (endDate < startDate) {
      status = 'End date must be on or after start date.';
      return;
    }
    if (selected.size === 0) {
      status = 'Select at least one data source.';
      return;
    }

    busy = true;
    try {
      const params = new URLSearchParams({
        sources: Array.from(selected).join(','),
        start_date: startDate,
        end_date: endDate
      });

      if (selectedActivityIds.size > 0) {
        params.set('activity_ids', Array.from(selectedActivityIds).join(','));
      }

      const response = await fetch(`/api/export/csv?${params.toString()}`);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = `export_${startDate}_${endDate}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);

      status = 'Export downloaded successfully.';
    } catch (error) {
      status = `Export failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  onMount(loadCatalog);
</script>

<section class="hero">
  <h2>Export Data to CSV</h2>
  <p>Select a date range and one or more data sources to download a merged CSV export.</p>
</section>

<section class="card export-card">
  <div class="grid two">
    <label>
      <div class="label">From</div>
      <input type="date" bind:value={startDate} />
    </label>
    <label>
      <div class="label">To</div>
      <input type="date" bind:value={endDate} />
    </label>
  </div>

  <div class="label block-gap">Data Sources</div>
  <div class="source-grid">
    {#each sourceOptions as source}
      <label class="source-item">
        <input
          type="checkbox"
          checked={selected.has(source.value)}
          on:change={() => toggleSource(source.value)}
        />
        <span>{source.label}</span>
      </label>
    {/each}
  </div>

  <div class="label block-gap">Filter Export by Activities <span class="hint-inline">(optional)</span></div>
  <p class="hint">If selected, the export includes only dates where at least one selected activity was tagged in Mood Log.</p>

  <section class="card acts-card">
    <div class="acts-header">
      <h3 style="margin:0;">Activities</h3>
      <span class="label" style="flex:1;margin:0;">Tap chips to toggle, then switch categories using tabs.</span>
      <button type="button" class="btn-clear" on:click={clearActivities}>Clear</button>
    </div>

    {#if selectedActivityIds.size > 0}
      <div class="selected-summary">
        {#each Array.from(selectedActivityIds) as id}
          {@const act = activities.find(a => a.id === id)}
          {#if act}
            <button class="chip chip-selected" on:click={() => toggleActivity(id)}>{act.name} ×</button>
          {/if}
        {/each}
      </div>
    {/if}

    {#if categories.length === 0}
      <p class="hint">Loading categories…</p>
    {:else}
      <div class="cat-tabs">
        {#each categories as cat, i}
          <button
            type="button"
            class="cat-tab"
            class:cat-tab-active={activeCategory === i}
            on:click={() => (activeCategory = i)}
          >
            {cat.name}
            {#if byCategory(cat.id).some(a => selectedActivityIds.has(a.id))}
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
              type="button"
              class="chip"
              class:chip-selected={selectedActivityIds.has(activity.id)}
              on:click={() => toggleActivity(activity.id)}
            >{activity.name}</button>
          {:else}
            <p class="hint">No activities in this category.</p>
          {/each}
        </div>
      {/if}
    {/if}

    <div class="acts-footer">
      <button type="button" class="btn-subtle" on:click={selectAllActivities}>Select all</button>
      <span class="selected-count">{selectedActivityIds.size} selected</span>
    </div>
  </section>

  <div class="actions">
    <button class="btn-primary" disabled={busy} on:click={exportCsv}>
      {busy ? 'Exporting...' : 'Export CSV'}
    </button>
  </div>

  {#if status}
    <p class="status-msg">{status}</p>
  {/if}
</section>

<style>
  .export-card { padding: 1rem; }
  .block-gap { margin-top: 0.9rem; }
  .hint-inline { font-size: 0.82rem; color: #496685; font-weight: 400; }
  .source-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }
  .source-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border: 1px solid #d7e6f7;
    border-radius: 10px;
    background: #f8fbff;
    padding: 0.55rem 0.65rem;
    color: #1e4b76;
    font-size: 0.9rem;
  }
  .source-item input { width: auto; }
  .actions {
    margin-top: 1rem;
    display: flex;
    justify-content: center;
  }
  .btn-primary {
    background: #3c79c5;
    border-color: #3168ad;
    color: #fff;
    min-width: 170px;
    font-weight: 700;
  }
  .status-msg {
    margin-top: 0.75rem;
    font-size: 0.9rem;
    color: #22543d;
    background: #d4edda;
    border-radius: 8px;
    padding: 0.4rem 0.6rem;
  }
  .hint {
    margin: 0.3rem 0 0.65rem;
    color: #486888;
    font-size: 0.85rem;
  }
  /* Activity picker — matches mood-entry style */
  .acts-card { margin-top: 0.1rem; padding: 0.75rem 0.9rem; }
  .acts-header { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.55rem; }
  .acts-footer { display: flex; align-items: center; gap: 0.6rem; margin-top: 0.75rem; border-top: 1px solid #e8f0f9; padding-top: 0.55rem; }
  .selected-summary { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e8f0f9; }
  .cat-tabs { display: flex; flex-wrap: wrap; gap: 0.3rem; border-bottom: 2px solid #e2eaf4; margin-bottom: 0.6rem; padding-bottom: 0.35rem; }
  .cat-tab { position: relative; background: transparent; border: 1px solid #d7e6f7; border-radius: 999px; padding: 0.3rem 0.65rem; font-size: 0.82rem; color: #1e4b76; cursor: pointer; }
  .cat-tab-active { background: #d4e9ff; border-color: #a9c9ea; font-weight: 700; }
  .cat-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #3c79c5; margin-left: 4px; vertical-align: middle; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.3rem; }
  .chip { background: #ecf2fb; border: 1px solid #ccddf4; color: #1f4066; border-radius: 999px; padding: 0.3rem 0.75rem; font-size: 0.84rem; cursor: pointer; transition: all 0.1s; }
  .chip-selected { background: #3c79c5; border-color: #3168ad; color: #fff; }
  .btn-clear { background: transparent; border-color: #c7d9ef; color: #496685; font-size: 0.84rem; padding: 0.3rem 0.7rem; white-space: nowrap; }
  .btn-subtle { background: #edf4fd; border-color: #c7d9ef; color: #355f89; font-size: 0.82rem; padding: 0.24rem 0.55rem; }
  .selected-count { color: #486888; font-size: 0.82rem; }

  @media (max-width: 860px) {
    .source-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 540px) {
    .source-grid { grid-template-columns: 1fr; }
  }
</style>
