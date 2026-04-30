<script lang="ts">
  import '../app.css';
  import { page } from '$app/stores';

  const links = [
    { href: '/mood-entry', label: 'Mood Entry' },
    { href: '/mood-log', label: 'Mood Log' },
    { href: '/garmin-log', label: 'Garmin Log' },
    { href: '/analytics', label: 'Analytics' },
    { href: '/settings', label: 'Settings' }
  ];
</script>

<header class="topbar">
  <div class="topbar-inner">
    <h1>Sleep Wellness Tracker</h1>
    <nav>
      {#each links as link}
<<<<<<< HEAD
        <a href={link.href} class:active={$page.url.pathname === link.href || $page.url.pathname.startsWith(link.href + '/')}>{link.label}</a>
=======
        <a href={link.href} class:active={$page.url.pathname === link.href}>{link.label}</a>
>>>>>>> feat/new-frontend-sveltekit
      {/each}
    </nav>
  </div>
</header>

<main>
  <slot />
</main>

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
</style>
