<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, postJson, putJson } from '$lib/api';
  import type { Category } from '$lib/types';

  let categories: Category[] = [];
  let name = '';
  let status = '';

  const load = async () => {
    try {
      categories = await getJson<Category[]>('/categories/');
    } catch (error) {
      status = `Load failed: ${error}`;
    }
  };

  const add = async () => {
    if (!name.trim()) return;
    status = '';
    try {
      await postJson('/categories/', { name: name.trim(), require_rating: 1, rating_label: null });
      name = '';
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
        rating_label: cat.rating_label || null
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

  onMount(load);
</script>

<section class="hero">
  <h2>Manage Categories</h2>
  <p>Create, edit, and remove categories while preserving existing API behavior.</p>
</section>

<section class="card">
  <h3>Add Category</h3>
  <div style="display:flex; gap:0.5rem;">
    <input placeholder="Category name" bind:value={name} />
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
        </div>
        <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
          <button on:click={() => save(category)}>Save</button>
          <button on:click={() => remove(category.id)}>Delete</button>
        </div>
      </div>
    {/each}
  {/if}
</section>
