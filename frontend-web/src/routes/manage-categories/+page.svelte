<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, postJson, putJson } from '$lib/api';
  import type { Category, PositionOption } from '$lib/types';

  let categories: Category[] = [];
  let positionOptions: PositionOption[] = [];
  let name = '';
  let newSupportsPosition = false;
  let newPositionLabel = '';
  let status = '';

  const load = async () => {
    try {
      [categories, positionOptions] = await Promise.all([
        getJson<Category[]>('/categories/'),
        getJson<PositionOption[]>('/categories/position-options/')
      ]);
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  const add = async () => {
    if (!name.trim()) return;
    status = '';
    try {
      await postJson('/categories/', {
        name: name.trim(),
        require_rating: 1,
        rating_label: null,
        supports_position: newSupportsPosition
      });
      name = '';
      newSupportsPosition = false;
      await load();
    } catch (error) {
      status = `Add failed: ${error}`;
    }
  };

  const save = async (cat: Category) => {
    status = '';
    try {
      await putJson(`/categories/${cat.id}`, {
        name: cat.name,
        require_rating: Number(cat.require_rating ?? 1),
        rating_label: cat.rating_label || null,
        supports_position: Boolean(cat.supports_position)
      });
      await load();
    } catch (error) {
      status = `Save failed: ${error}`;
    }
  };

  const remove = async (id: number) => {
    if (!confirm('Delete this category?')) return;
    status = '';
    try {
      await deleteJson(`/categories/${id}`);
      await load();
    } catch (error) {
      status = `Delete failed: ${error}`;
    }
  };

  const addPositionOption = async () => {
    if (!newPositionLabel.trim()) return;
    status = '';
    try {
      await postJson('/categories/position-options/', { label: newPositionLabel.trim() });
      newPositionLabel = '';
      await load();
    } catch (error) {
      status = `Add position failed: ${error}`;
    }
  };

  const savePositionOption = async (option: PositionOption) => {
    status = '';
    try {
      await putJson(`/categories/position-options/${option.id}`, { label: option.label });
      await load();
    } catch (error) {
      status = `Save position failed: ${error}`;
    }
  };

  const removePositionOption = async (id: number) => {
    if (!confirm('Delete this position option?')) return;
    status = '';
    try {
      await deleteJson(`/categories/position-options/${id}`);
      await load();
    } catch (error) {
      status = `Delete position failed: ${error}`;
    }
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Manage Categories</h2>
  <p>Create, edit, and remove categories while preserving existing API behavior.</p>
</section>

<section class="card">
  <h3>Add Category</h3>
  <div style="display:flex; gap:0.5rem; align-items:center;">
    <input placeholder="Category name" bind:value={name} />
    <label style="display:flex; gap:0.4rem; align-items:center;">
      <input type="checkbox" bind:checked={newSupportsPosition} />
      <span>Supports position</span>
    </label>
    <button on:click={add}>Add</button>
    <button on:click={load}>Refresh</button>
  </div>
  {#if status}<p>{status}</p>{/if}
</section>

<section class="card">
  <h3>Existing Categories</h3>
  {#if categories.length === 0}
    <p>No categories found.</p>
  {:else}
    {#each categories as category (category.id)}
      <div class="card" style="margin-bottom:0.6rem;">
        <div class="grid three">
          <label>
            <div class="label">Name</div>
            <input bind:value={category.name} />
          </label>
          <label>
            <div class="label">Require Rating</div>
            <select bind:value={category.require_rating}>
              <option value={1}>Yes</option>
              <option value={0}>No</option>
            </select>
          </label>
          <label>
            <div class="label">Rating Label</div>
            <input bind:value={category.rating_label} placeholder="Mood Score" />
          </label>
          <label style="display:flex; gap:0.5rem; align-items:end; padding-bottom:0.35rem;">
            <input type="checkbox" bind:checked={category.supports_position} />
            <span>Supports position (default for new activities)</span>
          </label>
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
          <button on:click={() => save(category)}>Save</button>
          <button on:click={() => remove(category.id)}>Delete</button>
        </div>
      </div>
    {/each}
  {/if}
</section>

<section class="card">
  <h3>Position Options</h3>
  <p>Options available when tagging a position-sensitive activity or category (e.g. Left, Right, Front).</p>
  {#each positionOptions as option (option.id)}
    <div style="display:flex; gap:0.5rem; align-items:center; margin-bottom:0.4rem;">
      <input bind:value={option.label} />
      <button on:click={() => savePositionOption(option)}>Save</button>
      <button on:click={() => removePositionOption(option.id)}>Delete</button>
    </div>
  {/each}
  <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
    <input placeholder="New position label" bind:value={newPositionLabel} />
    <button on:click={addPositionOption}>Add</button>
  </div>
</section>
