<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, postJson, putJson } from '$lib/api';
  import type { Activity, Category } from '$lib/types';

  let categories: Category[] = [];
  let activities: Activity[] = [];
  let status = '';
  let newName = '';
  let newCategoryId = '';
  let newSupportsPosition = false;
  let filterCategoryId = '';

  const load = async () => {
    try {
      [categories, activities] = await Promise.all([
        getJson<Category[]>('/categories/'),
        getJson<Activity[]>('/activities/?include_archived=true&include_deprecated=true')
      ]);
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  // Default the new activity's position toggle from its category (still overridable before saving).
  const onCategoryChange = () => {
    const category = categories.find((c) => String(c.id) === newCategoryId);
    newSupportsPosition = Boolean(category?.supports_position);
  };

  const add = async () => {
    if (!newName.trim()) return;
    status = '';
    try {
      await postJson('/activities/', {
        name: newName.trim(),
        category_id: newCategoryId ? Number(newCategoryId) : null,
        supports_position: newSupportsPosition
      });
      newName = '';
      newSupportsPosition = false;
      await load();
    } catch (error) {
      status = `Add failed: ${error}`;
    }
  };

  const save = async (activity: Activity) => {
    status = '';
    try {
      const normalizedCategoryId =
        activity.category_id === null || activity.category_id === undefined
          ? null
          : Number(activity.category_id);

      await putJson(`/activities/${activity.id}`, {
        name: activity.name,
        category_id: normalizedCategoryId,
        supports_position: Boolean(activity.supports_position)
      });
      await load();
    } catch (error) {
      status = `Save failed: ${error}`;
    }
  };

  const remove = async (id: number) => {
    if (!confirm('Delete this activity?')) return;
    status = '';
    try {
      await deleteJson(`/activities/${id}`);
      await load();
    } catch (error) {
      status = `Delete failed: ${error}`;
    }
  };

  const archive = async (id: number) => {
    status = '';
    try {
      await putJson(`/activities/${id}/archive`, {}); // Provide second argument
      await load();
    } catch (error) {
      status = `Archive failed: ${error}`;
    }
  };

  const unarchive = async (id: number) => {
    status = '';
    try {
      await putJson(`/activities/${id}/unarchive`, {}); // Provide second argument
      await load();
    } catch (error) {
      status = `Unarchive failed: ${error}`;
    }
  };

  const categoryName = (id: number | null | undefined) =>
    categories.find((c) => c.id === id)?.name || '(uncategorized)';

  $: filtered = filterCategoryId
    ? activities.filter((a) => String(a.category_id ?? '') === String(filterCategoryId))
    : activities;

  $: activeActivities = filtered.filter((a) => !a.is_archived); // Ensure 'is_archived' is used correctly
  $: archivedActivities = filtered.filter((a) => a.is_archived);

  onMount(load);
</script>

<section class="hero">
  <h2>Manage Activities</h2>
  <p>Manage activity labels and category mapping for mood entry and analytics pages.</p>
</section>

<section class="card">
  <h3>Add Activity</h3>
  <div class="grid three">
    <label>
      <div class="label">Name</div>
      <input bind:value={newName} placeholder="Activity name" />
    </label>
    <label>
      <div class="label">Category</div>
      <select bind:value={newCategoryId} on:change={onCategoryChange}>
        <option value="">(uncategorized)</option>
        {#each categories as category}
          <option value={category.id}>{category.name}</option>
        {/each}
      </select>
    </label>
    <label style="display:flex; gap:0.5rem; align-items:end; padding-bottom:0.35rem;">
      <input type="checkbox" bind:checked={newSupportsPosition} />
      <span>Supports position</span>
    </label>
    <div style="display:flex; align-items:end;">
      <button on:click={add}>Add</button>
    </div>
  </div>
  {#if status}<p>{status}</p>{/if}
</section>

<section class="card">
  <h3>Existing Activities</h3>
  <label style="max-width:320px; display:block; margin-bottom:0.7rem;">
    <div class="label">Filter by Category</div>
    <select bind:value={filterCategoryId}>
      <option value="">(all)</option>
      {#each categories as category}
        <option value={category.id}>{category.name}</option>
      {/each}
    </select>
  </label>

  {#if filtered.length === 0}
    <p>No activities found.</p>
  {:else}
    {#each filtered as activity (activity.id)}
      <div class="card" style="margin-bottom:0.5rem;">
        <div class="grid three">
          <label>
            <div class="label">Name</div>
            <input bind:value={activity.name} />
          </label>
          <label>
            <div class="label">Category</div>
            <select bind:value={activity.category_id}>
              <option value={''}>(uncategorized)</option>
              {#each categories as category}
                <option value={category.id}>{category.name}</option>
              {/each}
            </select>
          </label>
          <label style="display:flex; gap:0.5rem; align-items:end; padding-bottom:0.35rem;">
            <input type="checkbox" bind:checked={activity.supports_position} />
            <span>Supports position</span>
          </label>
          <div>
            <div class="label">Current</div>
            <p class="badge">{categoryName(activity.category_id)}</p>
          </div>
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
          <button on:click={() => save(activity)}>Save</button>
          <button on:click={() => remove(activity.id)}>Delete</button>
        </div>
      </div>
    {/each}
  {/if}
</section>

<section>
  <h3>Active Activities</h3>
  <ul>
    {#each activeActivities as activity}
      <li>
        {activity.name} ({categoryName(activity.category_id)})
        <button on:click={() => archive(activity.id)}>Archive</button>
      </li>
    {/each}
  </ul>
</section>

<section>
  <h3>Archived Activities</h3>
  <ul>
    {#each archivedActivities as activity}
      <li>
        {activity.name} ({categoryName(activity.category_id)})
        <button on:click={() => unarchive(activity.id)}>Unarchive</button>
      </li>
    {/each}
  </ul>
</section>
