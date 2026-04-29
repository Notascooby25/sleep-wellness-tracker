<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson } from '$lib/api';
  import type { Activity, MoodEntry } from '$lib/types';

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
  let status = '';
  let loading = false;
  const PAGE_SIZE = 100;
  let hasMore = true;
  let loadingMore = false;

  const fmtDate = (ts: string) => new Date(ts).toLocaleString('en-GB', { hour12: false });

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

  onMount(load);
</script>

<section class="hero">
  <h2>Mood Log</h2>
  <p>Review entries, activities, and remove records while keeping original backend routes.</p>
</section>

<section class="card">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem;">
    <h3 style="margin:0;">Entries ({entries.length})</h3>
    <button on:click={load} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
  </div>
  {#if status}<p>{status}</p>{/if}

  {#if entries.length === 0}
    <p>No entries found.</p>
  {:else}
    <p class="label" style="margin-top:0.45rem;">
      Loaded {entries.length} entries
    </p>

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
          <tr>
            <td>{fmtDate(entry.timestamp)}</td>
            <td>{entry.mood_score ?? 'n/a'}</td>
            <td>{entry.notes || '-'}</td>
            <td>
              {#if entry.activity_ids?.length}
                {#each entry.activity_ids as aid}
                  <span class="badge" style="margin-right:0.25rem;">{activityName(aid)}</span>
                {/each}
              {:else}
                -
              {/if}
            </td>
            <td>
              {#if entry.id !== undefined}
                <button on:click={() => remove(entry.id)}>Delete</button>
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>

    {#if hasMore}
      <div style="margin-top:0.6rem;">
        <button on:click={loadMore} disabled={loadingMore}>
          {loadingMore ? 'Loading...' : 'Load 100 More'}
        </button>
      </div>
    {/if}
  {/if}
</section>
