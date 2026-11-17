<script lang="ts">
  import { onMount } from 'svelte';
  import { updated } from '$app/stores';
  import { refreshToLatest } from '$lib/appUpdate';

  let refreshing = false;

  const update = async () => {
    if (refreshing) return;
    refreshing = true;
    await refreshToLatest();
    // If the reload didn't happen (server unreachable), let the user try again.
    refreshing = false;
  };

  onMount(() => {
    // A phone app resumed after hours in the background should re-check straight away.
    const onVisible = () => {
      if (document.visibilityState === 'visible') updated.check();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => document.removeEventListener('visibilitychange', onVisible);
  });
</script>

{#if $updated}
  <div class="update-banner" role="status">
    <span>A new version of the app is available.</span>
    <button type="button" on:click={update} disabled={refreshing}>
      {refreshing ? 'Updating…' : 'Update now'}
    </button>
  </div>
{/if}

<style>
  .update-banner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    padding: 0.45rem 1rem;
    background: #dceeff;
    border-bottom: 1px solid #9ec0e7;
    color: #173a5c;
    font-size: 0.9rem;
  }

  .update-banner button {
    background: #fff;
    border: 1px solid #9ec0e7;
    border-radius: 10px;
    color: #173a5c;
    padding: 0.3rem 0.8rem;
    font-weight: 600;
    cursor: pointer;
  }

  @media (pointer: coarse) {
    .update-banner button {
      min-height: 44px;
    }
  }
</style>
