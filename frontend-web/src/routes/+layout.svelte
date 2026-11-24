<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { registerServiceWorker } from '$lib/push';
  import UpdateBanner from '$lib/UpdateBanner.svelte';

  const links = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/mood-entry', label: 'Mood Entry' },
    { href: '/mood-log', label: 'Mood Log' },
    { href: '/garmin-log', label: 'Garmin Log' },
    { href: '/garmin-lifestyle-impact', label: 'Lifestyle Impact' },
    { href: '/analytics', label: 'Analytics' },
    { href: '/acupuncture-report', label: 'Acupuncture Report' },
    { href: '/settings', label: 'Settings' }
  ];

  let isOnline = true;
  let installPromptEvent: any = null;
  let showInstallButton = false;
  let menuOpen = false;

  const closeMenu = () => {
    menuOpen = false;
  };

  $: if ($page.url.pathname) {
    menuOpen = false;
  }

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
    <div class="offline-banner" role="status">Offline — can't reach the server. Some actions may not work until reconnected.</div>
  {/if}
  <header class="topbar">
    <div class="topbar-inner">
      <div class="topbar-row">
        <p class="brand">Sleep Wellness Tracker</p>
        <button
          type="button"
          class="burger-btn"
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          aria-expanded={menuOpen}
          on:click={() => (menuOpen = !menuOpen)}
        >
          {#if menuOpen}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          {:else}
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          {/if}
        </button>
      </div>
      <nav aria-label="Main" class="desktop-nav">
        {#each links as link}
          <a href={link.href} aria-current={$page.url.pathname === link.href || $page.url.pathname.startsWith(link.href + '/') ? 'page' : undefined} class:active={$page.url.pathname === link.href || $page.url.pathname.startsWith(link.href + '/')}>{link.label}</a>
        {/each}
        {#if showInstallButton}
          <button type="button" on:click={installApp} class="install-link">Install app</button>
        {/if}
        <button type="button" on:click={logout} class="logout-link">Log out</button>
      </nav>
    </div>
    {#if menuOpen}
      <div class="mobile-menu-backdrop" role="presentation" on:click={closeMenu}></div>
      <nav class="mobile-menu" aria-label="More pages">
        <p class="mobile-menu-heading">Reports</p>
        <a href="/garmin-lifestyle-impact" on:click={closeMenu} class:active={$page.url.pathname === '/garmin-lifestyle-impact' || $page.url.pathname.startsWith('/garmin-lifestyle-impact/')}>Lifestyle Impact</a>
        <a href="/analytics" on:click={closeMenu} class:active={$page.url.pathname === '/analytics' || $page.url.pathname.startsWith('/analytics/')}>Analytics</a>
        <a href="/acupuncture-report" on:click={closeMenu} class:active={$page.url.pathname === '/acupuncture-report' || $page.url.pathname.startsWith('/acupuncture-report/')}>Acupuncture Report</a>
        <hr class="mobile-menu-divider" />
        <a href="/settings" on:click={closeMenu} class:active={$page.url.pathname === '/settings' || $page.url.pathname.startsWith('/settings/')}>Settings</a>
        {#if showInstallButton}
          <button type="button" on:click={() => { closeMenu(); installApp(); }} class="mobile-menu-action install-action">Install app</button>
        {/if}
        <button type="button" on:click={() => { closeMenu(); logout(); }} class="mobile-menu-action">Log out</button>
      </nav>
    {/if}
  </header>

  <UpdateBanner />

  <main>
    <slot />
  </main>

  <nav class="bottom-nav" aria-label="Primary">
    <a href="/dashboard" aria-current={$page.url.pathname === '/dashboard' || $page.url.pathname.startsWith('/dashboard/') ? 'page' : undefined} class:active={$page.url.pathname === '/dashboard' || $page.url.pathname.startsWith('/dashboard/')}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
        <polyline points="9 22 9 12 15 12 15 22" />
      </svg>
      <span>Dashboard</span>
    </a>
    <a href="/mood-entry" aria-current={$page.url.pathname === '/mood-entry' || $page.url.pathname.startsWith('/mood-entry/') ? 'page' : undefined} class:active={$page.url.pathname === '/mood-entry' || $page.url.pathname.startsWith('/mood-entry/')}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
      </svg>
      <span>Mood Entry</span>
    </a>
    <a href="/mood-log" aria-current={$page.url.pathname === '/mood-log' || $page.url.pathname.startsWith('/mood-log/') ? 'page' : undefined} class:active={$page.url.pathname === '/mood-log' || $page.url.pathname.startsWith('/mood-log/')}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <line x1="8" y1="6" x2="21" y2="6" />
        <line x1="8" y1="12" x2="21" y2="12" />
        <line x1="8" y1="18" x2="21" y2="18" />
        <line x1="3" y1="6" x2="3.01" y2="6" />
        <line x1="3" y1="12" x2="3.01" y2="12" />
        <line x1="3" y1="18" x2="3.01" y2="18" />
      </svg>
      <span>Mood Log</span>
    </a>
  </nav>
{/if}

<style>
  .topbar {
    position: sticky;
    top: 0;
    z-index: 2;
    backdrop-filter: blur(8px);
    background: rgba(246, 250, 255, 0.9);
    border-bottom: 1px solid var(--color-neutral-border);
  }

  .topbar-inner {
    max-width: 1120px;
    margin: 0 auto;
    padding: 0.8rem 1rem;
  }

  .brand {
    margin: 0;
    font-size: 1.1rem;
    font-weight: 700;
    color: #11314f;
  }

  nav {
    margin-top: 0.45rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  nav a {
    border: 1px solid var(--color-input-border);
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: var(--color-link);
    background: var(--color-surface-subtle);
  }

  nav a.active {
    background: var(--color-primary);
    border-color: var(--color-primary-border-soft);
    font-weight: 700;
  }

  .logout-link {
    border: 1px solid var(--color-input-border);
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: var(--color-link);
    background: var(--color-surface-subtle);
    cursor: pointer;
  }

  .install-link {
    border: 1px solid var(--color-primary-border);
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.82rem;
    color: var(--color-neutral-bg);
    background: #0d6efd;
    cursor: pointer;
    font-weight: 600;
  }

  /* Touch screens: nav controls meet the 44px minimum target size. */
  @media (pointer: coarse) {
    nav a,
    .logout-link,
    .install-link {
      display: inline-flex;
      align-items: center;
      min-height: 44px;
    }
  }

  .topbar-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .burger-btn {
    display: none;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    min-height: 44px;
    padding: 0.4rem;
    border: 1px solid var(--color-input-border);
    border-radius: 10px;
    background: var(--color-surface-subtle);
    color: #11314f;
    cursor: pointer;
  }

  .mobile-menu-backdrop {
    position: fixed;
    inset: 0;
    z-index: 9;
    background: rgba(17, 49, 79, 0.25);
  }

  .mobile-menu {
    position: absolute;
    top: 100%;
    right: 0.75rem;
    z-index: 10;
    min-width: 220px;
    margin-top: 0.25rem;
    padding: 0.5rem;
    border-radius: 12px;
    background: var(--color-surface, #ffffff);
    border: 1px solid var(--color-neutral-border);
    box-shadow: 0 10px 28px rgba(17, 49, 79, 0.16);
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .mobile-menu-heading {
    margin: 0.25rem 0.6rem 0.1rem;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-text-muted, #5c6f84);
  }

  .mobile-menu a,
  .mobile-menu-action {
    display: flex;
    align-items: center;
    min-height: 44px;
    padding: 0.45rem 0.75rem;
    border-radius: 8px;
    font-size: 0.92rem;
    color: var(--color-link);
    text-decoration: none;
    background: transparent;
    border: none;
    text-align: left;
    cursor: pointer;
    width: 100%;
  }

  .mobile-menu a.active {
    background: var(--color-primary);
    font-weight: 700;
  }

  .mobile-menu-action.install-action {
    color: #0d6efd;
    font-weight: 600;
  }

  .mobile-menu-divider {
    border: 0;
    border-top: 1px solid var(--color-neutral-border);
    margin: 0.25rem 0;
  }

  .bottom-nav {
    display: none;
  }

  @media (max-width: 768px) {
    .topbar-inner {
      padding: 0.45rem 0.85rem;
    }

    .desktop-nav {
      display: none;
    }

    .burger-btn {
      display: inline-flex;
    }

    main {
      padding-bottom: calc(4.75rem + env(safe-area-inset-bottom, 0px));
    }

    .bottom-nav {
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 8;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      backdrop-filter: blur(8px);
      background: rgba(246, 250, 255, 0.95);
      border-top: 1px solid var(--color-neutral-border);
      padding-bottom: env(safe-area-inset-bottom, 0px);
    }

    .bottom-nav a {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.15rem;
      min-height: 54px;
      padding: 0.35rem 0.25rem;
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--color-text-muted, #4a6078);
      text-decoration: none;
    }

    .bottom-nav a.active {
      color: #0d6efd;
      font-weight: 700;
    }
  }

  .offline-banner {
    background: var(--color-error-bg);
    color: var(--color-error);
    text-align: center;
    font-size: 0.85rem;
    padding: 0.4rem 0.8rem;
  }
</style>
