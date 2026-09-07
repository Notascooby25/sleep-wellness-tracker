<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { registerServiceWorker } from '$lib/push';

  const links = [
    { href: '/mood-entry', label: 'Mood Entry' },
    { href: '/mood-log', label: 'Mood Log' },
    { href: '/garmin-log', label: 'Garmin Log' },
    { href: '/garmin-lifestyle-impact', label: 'Lifestyle Impact' },
    { href: '/analytics', label: 'Analytics' },
    { href: '/settings', label: 'Settings' }
  ];

  let isOnline = true;
  let installPromptEvent: any = null;
  let showInstallButton = false;

  const logout = async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    await goto('/login', { invalidateAll: true });
  };

  const installApp = async () => {
    if (!installPromptEvent) return;
    installPromptEvent.prompt();
    await installPromptEvent.userChoice;
    installPromptEvent = null;
    showInstallButton = false;
  };

  onMount(() => {
    registerServiceWorker();

    isOnline = navigator.onLine;
    const setOnline = () => (isOnline = true);
    const setOffline = () => (isOnline = false);
    window.addEventListener('online', setOnline);
    window.addEventListener('offline', setOffline);

    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault();
      if (isStandalone) return;
      installPromptEvent = event;
      showInstallButton = true;
    };
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    window.addEventListener('appinstalled', () => {
      showInstallButton = false;
      installPromptEvent = null;
    });

    return () => {
      window.removeEventListener('online', setOnline);
      window.removeEventListener('offline', setOffline);
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt);
    };
  });
</script>

{#if String($page.url.pathname) === '/login'}
  <main>
    <slot />
  </main>
{:else}
  {#if !isOnline}
    <div class="offline-banner">Offline — can't reach the server. Some actions may not work until reconnected.</div>
  {/if}
  <header class="topbar">
    <div class="topbar-inner">
      <h1>Sleep Wellness Tracker</h1>
      <nav>
        {#each links as link}
          <a href={link.href} class:active={$page.url.pathname === link.href || $page.url.pathname.startsWith(link.href + '/')}>{link.label}</a>
        {/each}
        {#if showInstallButton}
          <button on:click={installApp} class="install-link">Install app</button>
        {/if}
        <button on:click={logout} class="logout-link">Log out</button>
      </nav>
    </div>
  </header>

  <main>
    <slot />
  </main>
{/if}

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: 2;
    backdrop-filter: blur(8px);
    background: rgba(246, 250, 255, 0.9);
    border-bottom: 1px solid #d7e4f4;
  }

  .topbar-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 0.8rem 1rem;
  }

  h1 {
    margin: 0;
    font-size: 1.1rem;
    color: #11314f;
  }

  nav {
    margin-top: 0.45rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  nav a {
    border: 1px solid #cadcef;
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: #1e4b76;
    background: #edf4fd;
  }

  nav a.active {
    background: #d4e9ff;
    border-color: #a9c9ea;
    font-weight: 700;
  }

  .logout-link {
    border: 1px solid #cadcef;
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: #1e4b76;
    background: #edf4fd;
    cursor: pointer;
  }

  .install-link {
    border: 1px solid #9ec0e7;
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: #fff;
    background: #0d6efd;
    cursor: pointer;
    font-weight: 600;
  }

  .offline-banner {
    background: #fee4e2;
    color: #b42318;
    text-align: center;
    font-size: 0.85rem;
    padding: 0.4rem 0.8rem;
  }
</style>
