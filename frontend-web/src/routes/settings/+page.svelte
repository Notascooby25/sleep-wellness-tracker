<script lang="ts">
  import { describeError } from '$lib/errors.js';
  import { onMount } from 'svelte';
  import {
    pushSupported,
    subscribeThisDevice,
    listSubscriptions,
    removeSubscription,
    testSubscription,
    listReminders,
    createReminder,
    updateReminder,
    deleteReminder,
    type PushSubscriptionRow,
    type ReminderSchedule
  } from '$lib/push';
  import { api, putJson } from '$lib/api';
  import type { WeatherStatus } from '$lib/types';

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

  let weather: WeatherStatus | null = null;
  let weatherBusy = false;
  let weatherMessage = '';
  let weatherError = '';

  const loadWeather = async () => {
    try {
      weather = await api<WeatherStatus>(`/weather/status?fresh=${Date.now()}`);
    } catch (error) {
      weatherError = `Could not load weather status: ${describeError(error)}`;
    }
  };

  const fmtDay = (iso: string | null) =>
    iso ? new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '';

  const useCurrentLocation = () => {
    weatherError = '';
    weatherMessage = '';
    if (
      weather?.home_location_set &&
      !confirm(
        'Only do this if you have moved house. When you are just away, the app picks up local weather by itself. Change your home area to where you are now?'
      )
    ) {
      return;
    }
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
      weatherError = 'This browser cannot share your location.';
      return;
    }
    weatherBusy = true;
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          weather = await putJson<WeatherStatus>('/weather/home-location', {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude
          });
          weatherMessage = 'Home area saved. Weather is being fetched in the background. Tap "Check progress" in a minute. Weather already stored is kept.';
        } catch (error) {
          weatherError = `Could not save your home area: ${describeError(error)}`;
        } finally {
          weatherBusy = false;
        }
      },
      () => {
        weatherBusy = false;
        weatherError = 'Location was not shared. Allow location for this site in your browser settings, then try again.';
      },
      { enableHighAccuracy: false, timeout: 20000 }
    );
  };

  const addHeadacheCheckPreset = async () => {
    busyReminders = true;
    reminderError = '';
    try {
      await createReminder({
        time_of_day: '21:00',
        message: 'Headache today? Quick yes/no on Mood Entry',
        enabled: true
      });
      await load();
    } catch (error) {
      reminderError = `Could not add reminder: ${describeError(error)}`;
    } finally {
      busyReminders = false;
    }
  };

  const load = async () => {
    loadWeather();
    try {
      reminders = await listReminders();
    } catch (error) {
      reminderError = `Could not load reminders: ${describeError(error)}`;
    }
    try {
      subscriptions = await listSubscriptions();
    } catch (error) {
      subscriptionError = `Could not load devices: ${describeError(error)}`;
    }
  };

  onMount(() => {
    pushIsSupported = pushSupported();
    load();
  });

  const addPositivePreset = async () => {
    busyReminders = true;
    reminderError = '';
    try {
      await createReminder({
        time_of_day: '21:30',
        message: 'Evening check-in 🌿 Had a good health day? Tap to log a green score.',
        enabled: true
      });
      await load();
    } catch (error) {
      reminderError = `Could not add preset reminder: ${describeError(error)}`;
    } finally {
      busyReminders = false;
    }
  };

  const addReminder = async () => {
    busyReminders = true;
    reminderError = '';
    try {
      await createReminder({ time_of_day: newTime, message: newMessage.trim() || null, enabled: true });
      newMessage = '';
      await load();
    } catch (error) {
      reminderError = `Could not add reminder: ${describeError(error)}`;
    } finally {
      busyReminders = false;
    }
  };

  const toggleReminder = async (reminder: ReminderSchedule) => {
    try {
      await updateReminder(reminder.id, { enabled: !reminder.enabled });
      await load();
    } catch (error) {
      reminderError = `Could not update reminder: ${describeError(error)}`;
    }
  };

  const removeReminder = async (id: number) => {
    try {
      await deleteReminder(id);
      await load();
    } catch (error) {
      reminderError = `Could not delete reminder: ${describeError(error)}`;
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
      subscriptionError = `Could not enable notifications: ${describeError(error)}`;
    } finally {
      subscribeBusy = false;
    }
  };

  const removeDevice = async (id: number) => {
    try {
      await removeSubscription(id);
      await load();
    } catch (error) {
      subscriptionError = `Could not remove device: ${describeError(error)}`;
    }
  };

  const testDevice = async (id: number) => {
    subscriptionError = '';
    try {
      await testSubscription(id);
    } catch (error) {
      subscriptionError = `Could not send test push: ${describeError(error)}`;
    }
  };
</script>

<svelte:head>
  <title>Settings · Sleep Wellness Tracker</title>
</svelte:head>

<section class="hero">
  <h1>Settings</h1>
  <p>Configure advanced pages and management tools from one place.</p>
</section>

<section class="card reminder-card">
  <h3 style="margin:0 0 0.5rem;">Reminders</h3>
  <p style="margin:0 0 0.75rem;color:#5f6f84;font-size:0.88rem;">Push notifications sent to devices you enable below, at any times you add. They fire even if the app isn't open.</p>

  <h4 style="margin:0 0 0.4rem;font-size:0.92rem;">Notification devices</h4>
  {#if !pushIsSupported}
    <p class="notif-warn">Your browser does not support push notifications. Note: Android requires accessing the app via HTTPS (or localhost) for push to work.</p>
  {:else}
    <div class="reminder-row">
      <button type="button" on:click={enableThisDevice} disabled={subscribeBusy}>{subscribeBusy ? 'Enabling…' : 'Enable notifications on this device'}</button>
    </div>
    <div style="margin: 0.6rem 0 0.6rem 0; font-size: 0.84rem; color: var(--color-primary-content); background: var(--color-surface-subtle); border-radius: 8px; padding: 0.5rem 0.6rem;">
      <strong>Android users:</strong> If you use Brave, you must disable Brave Shields for this site. Also, ensure your browser's Battery Optimization is set to "Unrestricted" in Android settings.
    </div>
    {#if notifPermission === 'denied'}
      <p class="notif-warn">Notifications are blocked — allow them in your browser's site settings.</p>
    {/if}
  {/if}
  {#if subscriptionError}<p class="notif-warn" role="alert">{subscriptionError}</p>{/if}
  {#if subscriptions.length > 0}
    <ul class="device-list">
      {#each subscriptions as sub}
        <li>
          <span>{sub.device_label || 'Unnamed device'}</span>
          <button type="button" class="btn-clear" on:click={() => testDevice(sub.id)}>Test</button>
          <button type="button" class="btn-clear" on:click={() => removeDevice(sub.id)}>Remove</button>
        </li>
      {/each}
    </ul>
  {/if}

  <h4 style="margin:1rem 0 0.4rem;font-size:0.92rem;">Reminder times</h4>
  {#if reminderError}<p class="notif-warn" role="alert">{reminderError}</p>{/if}
  {#if reminders.length > 0}
    <ul class="device-list">
      {#each reminders as reminder}
        <li>
          <label class="chk" style="flex:0;">
            <input type="checkbox" checked={reminder.enabled} on:change={() => toggleReminder(reminder)} />
          </label>
          <span class="reminder-time">{reminder.time_of_day}</span>
          <span class="reminder-msg">{reminder.message || 'Update your tracker'}</span>
          <button type="button" class="btn-clear" on:click={() => removeReminder(reminder.id)}>Remove</button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="reminder-row">
    <input type="time" bind:value={newTime} style="width:auto;" />
    <input type="text" bind:value={newMessage} placeholder="Custom message (optional)" style="flex:1;min-width:160px;" />
    <button type="button" on:click={addReminder} disabled={busyReminders}>Add reminder</button>
  </div>
  <div style="margin-top: 0.75rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; background: #f0f7f3; border: 1px solid var(--color-success-bg); border-radius: 8px; padding: 0.6rem 0.8rem;">
    <span style="font-size: 0.84rem; color: #1f5e3d;">
      💡 <strong>Positive Habit Preset:</strong> Remind yourself at 21:30 to celebrate good health and log a green score.
    </span>
    <button type="button" on:click={addPositivePreset} disabled={busyReminders} style="font-size: 0.82rem; padding: 0.35rem 0.75rem; background: #2e8b57; color: white; border: none; border-radius: 6px; cursor: pointer;">
      + Add 21:30 Evening Check-In
    </button>
  </div>
  <div class="preset-row">
    <span><strong>Headache check:</strong> a 21:00 nudge to answer "Headache today?" on Mood Entry.</span>
    <button type="button" on:click={addHeadacheCheckPreset} disabled={busyReminders}>+ Add 21:00 Headache Check</button>
  </div>
</section>

<section class="card weather-card" aria-labelledby="weather-title">
  <h3 id="weather-title" style="margin:0 0 0.5rem;">Weather for the headache report</h3>
  <p class="weather-hint">
    The headache report can check whether changes in air pressure or temperature line up with your headaches.
    It needs your home area once. Only a rough position (to about 1 km) is stored and sent to the free Open-Meteo weather service.
  </p>
  <p class="weather-hint">
    When you're away from home, nothing to do: if your phone shares its location while you log, the app uses the local weather for those days instead.
  </p>
  {#if weather}
    {#if weather.home_location_set}
      <p class="weather-state">
        Home area is set.
        {#if weather.days_stored > 0}
          Weather stored for {weather.days_stored} days ({fmtDay(weather.first_date)} to {fmtDay(weather.last_date)}){#if weather.away_days}, including {weather.away_days} {weather.away_days === 1 ? 'day' : 'days'} away from home{/if}.
        {:else}
          No weather fetched yet.
        {/if}
      </p>
    {:else}
      <p class="weather-state">No home area set yet.</p>
    {/if}
  {/if}
  <div class="reminder-row">
    <button type="button" on:click={useCurrentLocation} disabled={weatherBusy}>
      {weatherBusy ? 'Finding you…' : weather?.home_location_set ? 'I\'ve moved house: use my current location' : 'Use my current location as home'}
    </button>
    {#if weather?.home_location_set}
      <button type="button" class="btn-clear" on:click={loadWeather}>Check progress</button>
    {/if}
  </div>
  {#if weatherMessage}<p class="weather-ok" role="status">{weatherMessage}</p>{/if}
  {#if weatherError}<p class="notif-warn" role="alert">{weatherError}</p>{/if}
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
  .weather-card { margin-bottom: 0.75rem; }
  .weather-hint { margin: 0 0 0.6rem; color: var(--color-neutral-text-muted); font-size: 0.88rem; }
  .weather-state { margin: 0 0 0.4rem; font-size: 0.9rem; color: var(--color-neutral-text); }
  .weather-ok { margin: 0.6rem 0 0; font-size: 0.84rem; color: var(--color-success-text); background: var(--color-success-bg); border-radius: 8px; padding: 0.3rem 0.6rem; }
  .preset-row { margin-top: 0.6rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; background: var(--color-surface-subtle); border: 1px solid var(--color-input-border); border-radius: 8px; padding: 0.6rem 0.8rem; font-size: 0.84rem; color: var(--color-primary-content); }
  .reminder-row { display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap; margin: 0.4rem 0; }
  .chk { display: flex; align-items: center; gap: 0.4rem; font-size: 0.9rem; cursor: pointer; }
  .chk input { width: auto; }
  .notif-warn { margin: 0.6rem 0 0; font-size: 0.84rem; color: var(--color-error); background: var(--color-error-bg); border-radius: 8px; padding: 0.3rem 0.6rem; }
  .device-list { list-style: none; margin: 0.4rem 0; padding: 0; display: flex; flex-direction: column; gap: 0.4rem; }
  .device-list li { display: flex; align-items: center; gap: 0.6rem; border: 1px solid var(--color-primary); border-radius: 8px; background: var(--color-bg-start); padding: 0.4rem 0.6rem; font-size: 0.86rem; }
  .device-list li span { flex: 1; }
  .reminder-time { font-weight: 700; color: var(--color-primary-content); flex: 0 0 auto !important; }
  .reminder-msg { color: var(--color-neutral-text-muted); }

  .settings-link {
    display: block;
    border: 1px solid var(--color-input-border);
    border-radius: 12px;
    background: var(--color-bg-start);
    padding: 0.9rem;
    transition: border-color 120ms ease, transform 120ms ease;
  }

  .settings-link:hover {
    border-color: var(--color-primary-border);
    transform: translateY(-1px);
  }

  .settings-link h3 {
    margin: 0 0 0.35rem;
    color: var(--color-primary-content);
  }

  .settings-link p {
    margin: 0;
    color: var(--color-neutral-text-muted);
    font-size: 0.92rem;
  }
</style>
