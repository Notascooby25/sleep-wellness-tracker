<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';

  let password = '';
  let status = '';
  let busy = false;
  let passwordInput: HTMLInputElement;

  // Put the cursor in the password box on arrival (done here, not with the autofocus attribute).
  onMount(() => passwordInput?.focus());

  const login = async () => {
    if (!password) return;
    busy = true;
    status = '';
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ password })
      });
      if (!response.ok) {
        status = 'Incorrect password.';
        return;
      }
      const redirectTo = $page.url.searchParams.get('redirect') || '/mood-entry';
      await goto(redirectTo, { invalidateAll: true });
    } catch (error) {
      status = `Login failed: ${error}`;
    } finally {
      busy = false;
    }
  };
</script>

<svelte:head>
  <title>Log in · Sleep Wellness Tracker</title>
</svelte:head>

<section class="hero">
  <h2>Sleep Wellness Tracker</h2>
  <p>Enter the password to continue.</p>
</section>

<section class="card" style="max-width:320px;">
  <form on:submit|preventDefault={login}>
    <label>
      <div class="label">Password</div>
      <input type="password" bind:value={password} bind:this={passwordInput} />
    </label>
    <button type="submit" disabled={busy} style="margin-top:0.75rem;">
      {busy ? 'Checking...' : 'Log in'}
    </button>
  </form>
  {#if status}<p>{status}</p>{/if}
</section>
