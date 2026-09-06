<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, putJson } from '$lib/api';
  import type { Activity, MoodEntry, PositionOption } from '$lib/types';

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
  let positionOptions: PositionOption[] = [];
  let status = '';
  let loading = false;
  const PAGE_SIZE = 100;
  let hasMore = true;
  let loadingMore = false;

  // Edit state
  let editId: number | null = null;
  let editScore: number | null = null;
  let editNotes = '';
  let editTimestamp = '';
  let editActivityIds = new Set<number>();
  let editActivityPositions = new Map<number, string[]>();
  let editImageUrls: string[] = [];
  let editActivityFilter = '';
  let editBusy = false;

  // Filter state
  let filterActivity = '';

  const fmtDate = (ts: string) => new Date(ts).toLocaleString('en-GB', { hour12: false });
  const toLocalInput = (ts: string) => {
    const d = new Date(ts);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };

  const activityName = (id: number) => activities.find((a) => a.id === id)?.name || `#${id}`;

  const chipLabel = (entry: MoodEntry, aid: number): string => {
    const name = activityName(aid);
    const details = (entry.activity_details ?? []).filter((d) => d.activity_id === aid);
    if (!details.length) return name;
    const suffix = details
      .map((d) => {
        const parts: string[] = [];
        if (d.position?.length) parts.push(d.position.join(', '));
        if (d.quantity_numeric != null) {
          parts.push(d.quantity_unit ? `${d.quantity_numeric} ${d.quantity_unit}` : String(d.quantity_numeric));
        }
        return parts.join(' / ');
      })
      .filter(Boolean)
      .join(', ');
    return suffix ? `${name} · ${suffix}` : name;
  };

  const entryImages = (entry: MoodEntry) => entry.image_urls?.length ? entry.image_urls : entry.image_url ? [entry.image_url] : [];

  const loadPage = async (offset: number) => {
    return getJson<MoodEntry[]>(`/mood/?limit=${PAGE_SIZE}&offset=${offset}`);
  };

  const load = async () => {
    loading = true;
    status = '';
    try {
      const [firstPage, acts, options] = await Promise.all([
        loadPage(0),
        getJson<Activity[]>('/activities/?include_archived=true&include_deprecated=true'),
        getJson<PositionOption[]>('/categories/position-options/').catch(() => [])
      ]);
      entries = firstPage;
      activities = acts;
      positionOptions = options;
      hasMore = firstPage.length === PAGE_SIZE;
    } catch (error) {
      status = `Load failed: ${error}`;
    } finally {
      loading = false;
    }
  };

  const loadMore = async () => {
    if (!hasMore || loadingMore) return;
    loadingMore = true;
    status = '';
    try {
      const next = await loadPage(entries.length);
      entries = [...entries, ...next];
      hasMore = next.length === PAGE_SIZE;
    } catch (error) {
      status = `Load more failed: ${error}`;
    } finally {
      loadingMore = false;
    }
  };

  const remove = async (id: number) => {
    if (!confirm(`Delete entry #${id}?`)) return;
    try {
      await deleteJson(`/mood/${id}`);
      await load();
    } catch (error) {
      status = `Delete failed: ${error}`;
    }
  };

  const startEdit = (entry: MoodEntry) => {
    editId = entry.id ?? null;
    editScore = entry.mood_score;
    editNotes = entry.notes ?? '';
    editTimestamp = toLocalInput(entry.timestamp);
    editActivityIds = new Set(entry.activity_ids || []);
    editActivityPositions = new Map(
      (entry.activity_details ?? []).map((detail) => [detail.activity_id, detail.position ?? []])
    );
    editImageUrls = entryImages(entry);
    editActivityFilter = '';
  };

  const cancelEdit = () => {
    editId = null;
    editActivityIds = new Set<number>();
    editActivityPositions = new Map<number, string[]>();
    editImageUrls = [];
    editActivityFilter = '';
  };

  const toggleEditPosition = (activityId: number, position: string) => {
    const next = new Map(editActivityPositions);
    const current = next.get(activityId) ?? [];
    next.set(
      activityId,
      current.includes(position)
        ? current.filter((value) => value !== position)
        : [...current, position]
    );
    editActivityPositions = next;
  };

  const toggleEditActivity = (id: number) => {
    const next = new Set(editActivityIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    editActivityIds = next;
  };

  $: filteredActivities = (() => {
    const q = editActivityFilter.trim().toLowerCase();
    if (!q) return activities;
    return activities.filter((a) => a.name.toLowerCase().includes(q));
  })();

  $: filteredEntries = (() => {
    const q = filterActivity.trim().toLowerCase();
    if (!q) return entries;
    const actMap = new Map(activities.map((a) => [a.id, a.name.toLowerCase()]));
    return entries.filter((entry) =>
      (entry.activity_ids || []).some((id) => actMap.get(id)?.includes(q))
    );
  })();

  const saveEdit = async () => {
    if (editId === null) return;
    editBusy = true;
    try {
      const ts = new Date(editTimestamp).toISOString();
      await putJson(`/mood/${editId}`, {
        mood_score: editScore,
        notes: editNotes.trim() || null,
        image_url: editImageUrls[0] ?? null,
        image_urls: editImageUrls,
        timestamp: ts,
        activity_ids: Array.from(editActivityIds),
        activity_details: Array.from(editActivityIds)
          .map((activity_id) => ({
            activity_id,
            position: editActivityPositions.get(activity_id) ?? []
          }))
          .filter((detail) => detail.position.length > 0)
      });
      editId = null;
      editActivityIds = new Set<number>();
      editActivityPositions = new Map<number, string[]>();
      editImageUrls = [];
      editActivityFilter = '';
      await load();
    } catch (error) {
      status = `Save failed: ${error}`;
    } finally {
      editBusy = false;
    }
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Mood Log</h2>
  <p>Review, edit, and remove mood entries.</p>
</section>

<section class="card">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem;">
    <h3 style="margin:0;">Entries ({filterActivity.trim() ? `${filteredEntries.length} of ${entries.length}` : entries.length})</h3>
    <button on:click={load} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
  </div>
  {#if status}<p class="status-msg">{status}</p>{/if}

  {#if entries.length === 0}
    <p>No entries found.</p>
  {:else}
    <div class="filter-row">
      <input
        type="text"
        bind:value={filterActivity}
        placeholder="Search activities..."
        class="filter-input"
      />
      {#if filterActivity}
        <button class="btn-sm clear-btn" on:click={() => (filterActivity = '')}>✕</button>
      {/if}
    </div>

    <p class="label" style="margin-top:0.45rem;">Loaded {entries.length} entries</p>

    {#if filteredEntries.length === 0}
      <p style="margin-top:0.5rem; color:#496685;">No entries match the activity filter.</p>
    {:else}
    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Mood</th>
            <th>Photos</th>
            <th>Notes</th>
            <th>Activities</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each filteredEntries as entry (entry.id)}
            {#if editId === entry.id}
              <tr class="edit-row">
                <td data-label="Date">
                  <input type="datetime-local" bind:value={editTimestamp} style="font-size:0.82rem;" />
                </td>
                <td data-label="Mood">
                  <input type="number" min="1" max="5" bind:value={editScore} style="width:4rem;" />
                </td>
                <td data-label="Photos">-</td>
                <td data-label="Notes">
                  <input type="text" bind:value={editNotes} placeholder="Notes…" />
                </td>
                <td data-label="Activities">
                  <div class="edit-acts">
                    <input type="text" bind:value={editActivityFilter} placeholder="Filter activities..." />
                    <div class="edit-acts-chips">
                      {#each filteredActivities as act}
                        <button
                          type="button"
                          class="act-chip"
                          class:act-chip-selected={editActivityIds.has(act.id)}
                          on:click={() => toggleEditActivity(act.id)}
                        >
                          {act.name}
                        </button>
                        {#if editActivityIds.has(act.id) && act.supports_position && positionOptions.length}
                          <div class="edit-position-chips">
                            {#each positionOptions as option}
                              <button
                                type="button"
                                class="position-chip"
                                class:position-chip-selected={(editActivityPositions.get(act.id) ?? []).includes(option.label)}
                                on:click={() => toggleEditPosition(act.id, option.label)}
                              >
                                {option.label}
                              </button>
                            {/each}
                          </div>
                        {/if}
                      {/each}
                    </div>
                  </div>
                </td>
                <td data-label="Actions" style="white-space:nowrap;">
                  <button class="btn-primary btn-sm" disabled={editBusy} on:click={saveEdit}>Save</button>
                  <button class="btn-sm" on:click={cancelEdit}>Cancel</button>
                </td>
              </tr>
            {:else}
              <tr>
                <td data-label="Date" style="white-space:nowrap;">{fmtDate(entry.timestamp)}</td>
                <td data-label="Mood">{entry.mood_score ?? 'n/a'}</td>
                <td data-label="Photos">
                  {#if entryImages(entry).length}
                    <div class="entry-photo-list">
                      {#each entryImages(entry) as imageUrl, index}
                        <a href={`/api${imageUrl}`} target="_blank" rel="noreferrer" aria-label={`Open mood photo ${index + 1}`}>
                          <img src={`/api${imageUrl}`} alt={`Mood attachment ${index + 1}`} class="entry-photo" loading="lazy" />
                        </a>
                      {/each}
                    </div>
                  {:else}
                    -
                  {/if}
                </td>
                <td data-label="Notes">{entry.notes || '-'}</td>
                <td data-label="Activities">
                  {#if entry.activity_ids?.length}
                    {#each entry.activity_ids as aid}
                      <span class="act-badge">{chipLabel(entry, aid)}</span>
                    {/each}
                  {:else}-{/if}
                </td>
                <td data-label="Actions" style="white-space:nowrap;">
                  {#if entry.id !== undefined}
                    <button class="btn-sm" on:click={() => startEdit(entry)}>Edit</button>
                    <button class="btn-sm btn-danger" on:click={() => remove(entry.id!)}>Delete</button>
                  {/if}
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>
    </div>

    {#if hasMore}
      <div style="margin-top:0.6rem;">
        <button on:click={loadMore} disabled={loadingMore}>
          {loadingMore ? 'Loading...' : 'Load 100 More'}
        </button>
      </div>
    {/if}
    {/if}
  {/if}
</section>

<style>
  .table-wrap { overflow-x: auto; margin-top: 0.5rem; }
  .table th, .table td { padding: 0.4rem 0.5rem; text-align: left; border-bottom: 1px solid #e8f0f9; font-size: 0.86rem; }
  .table th { font-size: 0.75rem; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; }
  .edit-row { background: #f0f7ff; }
  .edit-acts { min-width: 260px; }
  .edit-acts-chips { display: flex; flex-wrap: wrap; gap: 0.25rem; max-height: 130px; overflow: auto; margin-top: 0.35rem; }
  .edit-position-chips { display: flex; flex-wrap: wrap; gap: 0.25rem; margin: 0.2rem 0 0.35rem 0.4rem; }
  .position-chip { border: 1px solid #b9cce0; background: #fff; color: #315678; border-radius: 999px; padding: 0.18rem 0.45rem; font-size: 0.72rem; cursor: pointer; }
  .position-chip-selected { background: #315678; color: #fff; border-color: #315678; }
  .act-chip { background: #ecf2fb; border: 1px solid #ccddf4; color: #1f4066; border-radius: 999px; padding: 0.2rem 0.55rem; font-size: 0.75rem; cursor: pointer; }
  .act-chip-selected { background: #3c79c5; border-color: #3168ad; color: #fff; }
  .act-badge { display: inline-block; background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.1rem 0.45rem; font-size: 0.75rem; color: #1e4b76; margin: 0.1rem 0.15rem 0.1rem 0; }
  .entry-photo-list { display: flex; gap: 0.35rem; flex-wrap: wrap; }
  .entry-photo { width: 42px; height: 42px; object-fit: cover; border-radius: 8px; border: 1px solid #ccddf4; display: block; }
  .btn-sm { padding: 0.3rem 0.55rem; font-size: 0.8rem; margin-right: 0.2rem; }
  .btn-primary { background: #3c79c5; color: #fff; border-color: #3168ad; }
  .btn-danger { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
  .status-msg { font-size: 0.88rem; color: #22543d; background: #d4edda; border-radius: 8px; padding: 0.3rem 0.6rem; margin-top: 0.4rem; }
  .filter-row { display: flex; align-items: center; gap: 0.4rem; margin-top: 0.75rem; }
  .filter-input { flex: 1; max-width: 280px; padding: 0.3rem 0.55rem; font-size: 0.85rem; border: 1px solid #ccddf4; border-radius: 6px; background: #f5f9ff; color: #1f4066; }
  .filter-input:focus { outline: none; border-color: #3c79c5; background: #fff; }
  .clear-btn { background: #ecf2fb; border-color: #ccddf4; color: #496685; }
  @media (max-width: 760px) {
    .table-wrap { overflow-x: visible; }
    .table, .table tbody, .table tr, .table td { display: block; width: 100%; }
    .table thead { display: none; }
    .table tr {
      border: 1px solid #dbe8f8;
      border-radius: 10px;
      margin-bottom: 0.65rem;
      padding: 0.4rem 0.55rem;
      background: #fff;
    }
    .table td {
      display: flex;
      justify-content: flex-start;
      align-items: flex-start;
      gap: 0.65rem;
      border-bottom: none;
      padding: 0.28rem 0;
      white-space: normal !important;
      word-break: normal;
      overflow-wrap: anywhere;
    }
    .table td::before {
      content: attr(data-label);
      flex: 0 0 5.2rem;
      color: #496685;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.03em;
      text-transform: uppercase;
      min-width: 5.2rem;
    }
    .table td[data-label='Photos'],
    .table td[data-label='Activities'],
    .table td[data-label='Actions'] {
      display: block;
    }
    .table td[data-label='Photos']::before,
    .table td[data-label='Activities']::before,
    .table td[data-label='Actions']::before {
      display: block;
      margin-bottom: 0.28rem;
    }
    .table td[data-label='Actions'] { flex-wrap: wrap; }
    .table td[data-label='Actions']::before { margin-right: auto; }
    .act-badge {
      flex: 0 0 auto;
      white-space: nowrap;
      word-break: normal;
      overflow-wrap: normal;
    }
    .edit-acts { min-width: 0; width: 100%; }
    .btn-sm { margin-bottom: 0.2rem; }
  }
</style>
