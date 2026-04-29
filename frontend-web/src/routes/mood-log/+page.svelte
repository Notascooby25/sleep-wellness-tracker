<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, putJson } from '$lib/api';
  import type { Activity, MoodEntry } from '$lib/types';

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
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
  let editBusy = false;

  const fmtDate = (ts: string) => new Date(ts).toLocaleString('en-GB', { hour12: false });
  const toLocalInput = (ts: string) => new Date(ts).toISOString().slice(0, 16);

  const activityName = (id: number) => activities.find((a) => a.id === id)?.name || `#${id}`;

  const loadPage = async (offset: number) => {
    return getJson<MoodEntry[]>(`/mood/?limit=${PAGE_SIZE}&offset=${offset}`);
  };

  const load = async () => {
    loading = true;
    status = '';
    try {
      const [firstPage, acts] = await Promise.all([
        loadPage(0),
        getJson<Activity[]>('/activities/')
      ]);
      entries = firstPage;
      activities = acts;
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
  };

  const cancelEdit = () => {
    editId = null;
  };

  const saveEdit = async () => {
    if (editId === null) return;
    editBusy = true;
    try {
      const ts = new Date(editTimestamp).toISOString();
      const entry = entries.find(e => e.id === editId);
      await putJson(`/mood/${editId}`, {
        mood_score: editScore,
        notes: editNotes.trim() || null,
        timestamp: ts,
        activity_ids: entry?.activity_ids ?? []
      });
      editId = null;
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
    <h3 style="margin:0;">Entries ({entries.length})</h3>
    <button on:click={load} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
  </div>
  {#if status}<p class="status-msg">{status}</p>{/if}

  {#if entries.length === 0}
    <p>No entries found.</p>
  {:else}
    <p class="label" style="margin-top:0.45rem;">Loaded {entries.length} entries</p>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Mood</th>
            <th>Notes</th>
            <th>Activities</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each entries as entry (entry.id)}
            {#if editId === entry.id}
              <tr class="edit-row">
                <td>
                  <input type="datetime-local" bind:value={editTimestamp} style="font-size:0.82rem;" />
                </td>
                <td>
                  <input type="number" min="1" max="5" bind:value={editScore} style="width:4rem;" />
                </td>
                <td colspan="2">
                  <input type="text" bind:value={editNotes} placeholder="Notes…" />
                </td>
                <td style="white-space:nowrap;">
                  <button class="btn-primary btn-sm" disabled={editBusy} on:click={saveEdit}>Save</button>
                  <button class="btn-sm" on:click={cancelEdit}>Cancel</button>
                </td>
              </tr>
            {:else}
              <tr>
                <td style="white-space:nowrap;">{fmtDate(entry.timestamp)}</td>
                <td>{entry.mood_score ?? 'n/a'}</td>
                <td>{entry.notes || '-'}</td>
                <td>
                  {#if entry.activity_ids?.length}
                    {#each entry.activity_ids as aid}
                      <span class="act-badge">{activityName(aid)}</span>
                    {/each}
                  {:else}-{/if}
                </td>
                <td style="white-space:nowrap;">
                  {#if entry.id !== undefined}
                    <button class="btn-sm" on:click={() => startEdit(entry)}>Edit</button>
                    <button class="btn-sm btn-danger" on:click={() => remove(entry.id)}>Delete</button>
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
</section>

<style>
  .table-wrap { overflow-x: auto; margin-top: 0.5rem; }
  .table th, .table td { padding: 0.4rem 0.5rem; text-align: left; border-bottom: 1px solid #e8f0f9; font-size: 0.86rem; }
  .table th { font-size: 0.75rem; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; }
  .edit-row { background: #f0f7ff; }
  .act-badge { display: inline-block; background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.1rem 0.45rem; font-size: 0.75rem; color: #1e4b76; margin: 0.1rem 0.15rem 0.1rem 0; }
  .btn-sm { padding: 0.3rem 0.55rem; font-size: 0.8rem; margin-right: 0.2rem; }
  .btn-primary { background: #3c79c5; color: #fff; border-color: #3168ad; }
  .btn-danger { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
  .status-msg { font-size: 0.88rem; color: #22543d; background: #d4edda; border-radius: 8px; padding: 0.3rem 0.6rem; margin-top: 0.4rem; }
</style>
