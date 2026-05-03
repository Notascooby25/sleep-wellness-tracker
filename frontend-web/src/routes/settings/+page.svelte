<script lang="ts">
  import { onMount } from 'svelte';
  import { version } from '$app/environment';
  // BUILD_DATE is injected by vite.config.ts
  const buildDate = __BUILD_DATE__;

  let reminderEnabled = false;
  let reminderTime = '21:00';
  let notifPermission = 'default';
  let savedMsg = '';

  onMount(() => {
    reminderEnabled = localStorage.getItem('moodReminderEnabled') === 'true';
    reminderTime = localStorage.getItem('moodReminderTime') || '21:00';
    notifPermission = typeof Notification !== 'undefined' ? Notification.permission : 'unsupported';
  });

  const saveReminder = async () => {
    if (reminderEnabled && notifPermission !== 'granted' && typeof Notification !== 'undefined') {
      notifPermission = await Notification.requestPermission();
    }
    localStorage.setItem('moodReminderEnabled', String(reminderEnabled));
    localStorage.setItem('moodReminderTime', reminderTime);
    savedMsg = 'Saved!';
    setTimeout(() => (savedMsg = ''), 2000);
  };
</script>

<section class="hero">
  <h2>Settings</h2>
  <p>Configure advanced pages and management tools from one place.</p>
</section>

<section class="card reminder-card">
  <h3 style="margin:0 0 0.5rem;">Mood Reminder</h3>
  <p style="margin:0 0 0.75rem;color:#5f6f84;font-size:0.88rem;">Receive a browser notification at a set time each day to log your mood. Saved per device in this browser only.</p>
  <div class="reminder-row">
    <label class="chk">
      <input type="checkbox" bind:checked={reminderEnabled} />
      Enable daily reminder
    </label>
    <label style="display:flex;align-items:center;gap:0.5rem;">
      <span class="label" style="margin:0;">Time</span>
      <input type="time" bind:value={reminderTime} style="width:auto;" />
    </label>
    <button on:click={saveReminder}>Save</button>
    {#if savedMsg}<span class="saved-msg">{savedMsg}</span>{/if}
  </div>
  {#if notifPermission === 'denied'}
    <p class="notif-warn">Browser notifications are blocked — allow them in your browser's site settings.</p>
  {:else if notifPermission === 'unsupported'}
    <p class="notif-warn">Your browser does not support notifications.</p>
  {/if}
</section>

<section class="card grid two">
  <a class="settings-link" href="/manage-categories">
    <h3>Manage Categories</h3>
    <p>Create, rename, and configure category rating behavior.</p>
  </a>

  <a class="settings-link" href="/manage-activities">
    <h3>Manage Activities</h3>
    <p>Add and edit activities, including category assignments.</p>
  </a>

  <a class="settings-link" href="/settings/mood-log-tools">
    <h3>Mood Log Tools</h3>
    <p>Import backups, bulk delete entries, and run rating cleanup tools.</p>
  </a>

  <a class="settings-link" href="/settings/export">
    <h3>Export Data</h3>
    <p>Download mood logs and Garmin data as a CSV for any date range.</p>
  </a>
</section>

<footer class="version-footer">
  <span>v{version}</span>
  <span class="sep">·</span>
  <span>Built {buildDate}</span>
</footer>

<style>
  .version-footer {
    margin-top: 2rem;
    text-align: center;
    font-size: 0.78rem;
    color: #9ab6cc;
    letter-spacing: 0.03em;
  }

  .sep {
    margin: 0 0.4em;
  }

  .reminder-card { margin-bottom: 0.75rem; }
  .reminder-row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
  .chk { display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem; cursor: pointer; }
  .chk input { width: auto; }
  .saved-msg { font-size: 0.85rem; color: #086c3a; font-weight: 600; }
  .notif-warn { margin: 0.6rem 0 0; font-size: 0.84rem; color: #b42318; background: #fee4e2; border-radius: 8px; padding: 0.3rem 0.6rem; }

  .settings-link {
    display: block;
    border: 1px solid #cfe0f3;
    border-radius: 12px;
    background: #f5faff;
    padding: 0.9rem;
    transition: border-color 120ms ease, transform 120ms ease;
  }

  .settings-link:hover {
    border-color: #9ec0e7;
    transform: translateY(-1px);
  }

  .settings-link h3 {
    margin: 0 0 0.35rem;
    color: #163c61;
  }

  .settings-link p {
    margin: 0;
    color: #486888;
    font-size: 0.92rem;
  }
</style>
