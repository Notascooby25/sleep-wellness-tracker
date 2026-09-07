<script lang="ts">
  import { onMount } from 'svelte';
  import {
    pushSupported,
    subscribeThisDevice,
    listSubscriptions,
    removeSubscription,
    listReminders,
    createReminder,
    updateReminder,
    deleteReminder,
    type PushSubscriptionRow,
    type ReminderSchedule
  } from '$lib/push';

  const appVersion = __APP_VERSION__;
  // BUILD_DATE is injected by vite.config.ts
  const buildDate = __BUILD_DATE__;

  let reminders: ReminderSchedule[] = [];
  let subscriptions: PushSubscriptionRow[] = [];
  let newTime = '21:00';
  let newMessage = '';
  let notifPermission = typeof Notification !== 'undefined' ? Notification.permission : 'unsupported';
  let pushIsSupported = false;
  let busyReminders = false;
  let subscribeBusy = false;
  let reminderError = '';
  let subscriptionError = '';

  const load = async () => {
    try {
      reminders = await listReminders();
    } catch (error) {
      reminderError = `Could not load reminders: ${error}`;
    }
    try {
      subscriptions = await listSubscriptions();
    } catch (error) {
      subscriptionError = `Could not load devices: ${error}`;
    }
  };

  onMount(() => {
    pushIsSupported = pushSupported();
    load();
  });

  const addReminder = async () => {
    busyReminders = true;
    reminderError = '';
    try {
      await createReminder({ time_of_day: newTime, message: newMessage.trim() || null, enabled: true });
      newMessage = '';
      await load();
    } catch (error) {
      reminderError = `Could not add reminder: ${error}`;
    } finally {
      busyReminders = false;
    }
  };

  const toggleReminder = async (reminder: ReminderSchedule) => {
    try {
      await updateReminder(reminder.id, { enabled: !reminder.enabled });
      await load();
    } catch (error) {
      reminderError = `Could not update reminder: ${error}`;
    }
  };

  const removeReminder = async (id: number) => {
    try {
      await deleteReminder(id);
      await load();
    } catch (error) {
      reminderError = `Could not delete reminder: ${error}`;
    }
  };

  const enableThisDevice = async () => {
    subscribeBusy = true;
    subscriptionError = '';
    try {
      await subscribeThisDevice();
      notifPermission = Notification.permission;
      await load();
    } catch (error) {
      subscriptionError = `Could not enable notifications: ${error}`;
    } finally {
      subscribeBusy = false;
    }
  };

  const removeDevice = async (id: number) => {
    try {
      await removeSubscription(id);
      await load();
    } catch (error) {
      subscriptionError = `Could not remove device: ${error}`;
    }
  };
</script>

<section class="hero">
  <h2>Settings</h2>
  <p>Configure advanced pages and management tools from one place.</p>
</section>

<section class="card reminder-card">
  <h3 style="margin:0 0 0.5rem;">Reminders</h3>
  <p style="margin:0 0 0.75rem;color:#5f6f84;font-size:0.88rem;">Push notifications sent to devices you enable below, at any times you add. They fire even if the app isn't open.</p>

  <h4 style="margin:0 0 0.4rem;font-size:0.92rem;">Notification devices</h4>
  {#if !pushIsSupported}
    <p class="notif-warn">Your browser does not support push notifications.</p>
  {:else}
    <div class="reminder-row">
      <button on:click={enableThisDevice} disabled={subscribeBusy}>{subscribeBusy ? 'Enabling…' : 'Enable notifications on this device'}</button>
    </div>
    {#if notifPermission === 'denied'}
      <p class="notif-warn">Notifications are blocked — allow them in your browser's site settings.</p>
    {/if}
  {/if}
  {#if subscriptionError}<p class="notif-warn">{subscriptionError}</p>{/if}
  {#if subscriptions.length > 0}
    <ul class="device-list">
      {#each subscriptions as sub}
        <li>
          <span>{sub.device_label || 'Unnamed device'}</span>
          <button class="btn-clear" on:click={() => removeDevice(sub.id)}>Remove</button>
        </li>
      {/each}
    </ul>
  {/if}

  <h4 style="margin:1rem 0 0.4rem;font-size:0.92rem;">Reminder times</h4>
  {#if reminderError}<p class="notif-warn">{reminderError}</p>{/if}
  {#if reminders.length > 0}
    <ul class="device-list">
      {#each reminders as reminder}
        <li>
          <label class="chk" style="flex:0;">
            <input type="checkbox" checked={reminder.enabled} on:change={() => toggleReminder(reminder)} />
          </label>
          <span class="reminder-time">{reminder.time_of_day}</span>
          <span class="reminder-msg">{reminder.message || 'Update your tracker'}</span>
          <button class="btn-clear" on:click={() => removeReminder(reminder.id)}>Remove</button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="reminder-row">
    <input type="time" bind:value={newTime} style="width:auto;" />
    <input type="text" bind:value={newMessage} placeholder="Custom message (optional)" style="flex:1;min-width:160px;" />
    <button on:click={addReminder} disabled={busyReminders}>Add reminder</button>
  </div>
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
  <span>v{appVersion}</span>
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
  .reminder-row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin: 0.4rem 0; }
  .chk { display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem; cursor: pointer; }
  .chk input { width: auto; }
  .notif-warn { margin: 0.6rem 0 0; font-size: 0.84rem; color: #b42318; background: #fee4e2; border-radius: 8px; padding: 0.3rem 0.6rem; }
  .device-list { list-style: none; margin: 0.4rem 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
  .device-list li { display: flex; align-items: center; gap: 0.6rem; border: 1px solid #d7e6f7; border-radius: 8px; background: #f8fbff; padding: 0.4rem 0.6rem; font-size: 0.86rem; }
  .device-list li span { flex: 1; }
  .reminder-time { font-weight: 700; color: #163c61; flex: 0 0 auto !important; }
  .reminder-msg { color: #486888; }

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
