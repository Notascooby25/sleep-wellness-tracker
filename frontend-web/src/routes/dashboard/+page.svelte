<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';
  import type { GarminLatestWrap } from '$lib/types';

  type SleepLatest = { date: string; total_sleep_minutes?: number; sleep_score?: number; };
  type BatteryLatest = { date: string; morning_value?: number; end_of_day_value?: number; };
  type HrvLatest = { date: string; weekly_avg?: number; baseline_low?: number; baseline_high?: number; };
  type StressLatest = { date: string; overall_stress_level?: number; };

  let latestSleep: SleepLatest | null = null;
  let latestBattery: BatteryLatest | null = null;
  let latestHrv: HrvLatest | null = null;
  let latestStress: StressLatest | null = null;
  let adviceMessage: string = "Loading your personalized advice...";
  let loadError = false;
  let isLoading = true;
  let lastSyncDate: string | null = null;

  const fmtMinutes = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${Math.floor(value / 60)}h ${String(value % 60).padStart(2, '0')}m`;
  };

  const load = async () => {
    loadError = false;
    isLoading = true;
    try {
      const [sleepWrap, batteryWrap, hrvWrap, stressWrap, adviceWrap] = await Promise.all([
        getJson<GarminLatestWrap<SleepLatest>>('/garmin/sleep/latest'),
        getJson<GarminLatestWrap<BatteryLatest>>('/garmin/body-battery/latest'),
        getJson<GarminLatestWrap<HrvLatest>>('/garmin/hrv/latest'),
        getJson<GarminLatestWrap<StressLatest>>('/garmin/stress/latest'),
        getJson<{advice: string}>('/lifestyle-impact/advice')
      ]);
      latestSleep = sleepWrap?.data || null;
      latestBattery = batteryWrap?.data || null;
      latestHrv = hrvWrap?.data || null;
      latestStress = stressWrap?.data || null;
      adviceMessage = adviceWrap?.advice || "Keep logging your activities to receive personalized predictive advice!";
      lastSyncDate = latestSleep?.date || latestBattery?.date || latestHrv?.date || latestStress?.date || null;
    } catch (error) {
      adviceMessage = "Unable to load advice right now. Please check server connectivity.";
      loadError = true;
    } finally {
      isLoading = false;
    }
  };

  onMount(() => {
    load();
  });

  $: readinessScore = (() => {
    const parts: Array<{ w: number; v: number }> = [];
    if (latestSleep?.sleep_score != null) {
      parts.push({ w: 0.4, v: latestSleep.sleep_score });
    }
    if (latestHrv?.weekly_avg != null) {
      let norm: number;
      if (latestHrv.baseline_low != null && latestHrv.baseline_high != null && latestHrv.baseline_high > latestHrv.baseline_low) {
        const band = latestHrv.baseline_high - latestHrv.baseline_low;
        norm = Math.min(100, Math.max(0, ((latestHrv.weekly_avg - latestHrv.baseline_low) / band) * 100));
      } else {
        norm = Math.min(100, Math.max(0, ((latestHrv.weekly_avg - 20) / 60) * 100));
      }
      parts.push({ w: 0.3, v: norm });
    }
    if (latestStress?.overall_stress_level != null) {
      parts.push({ w: 0.3, v: 100 - latestStress.overall_stress_level });
    }
    if (!parts.length) return null;
    const totalWeight = parts.reduce((s, p) => s + p.w, 0);
    return Math.round(parts.reduce((s, p) => s + p.w * p.v, 0) / totalWeight);
  })();

  $: readinessTier = readinessScore === null ? 'unknown'
    : readinessScore >= 70 ? 'high'
    : readinessScore >= 50 ? 'moderate'
    : 'low';

  $: readinessStatus = readinessTier === 'high' ? 'Ready for action · High vitality'
    : readinessTier === 'moderate' ? 'Balanced pace · Steady rhythm'
    : readinessTier === 'low' ? 'Gentle pace recommended · Restorative day ahead'
    : 'Awaiting sync';

  $: readinessTheme = readinessTier === 'high' ? {
      text: '#215c43',
      bg: '#eaf5ee',
      border: '#b8dfcb'
    }
    : readinessTier === 'moderate' ? {
      text: '#2b4360',
      bg: '#edf3f9',
      border: '#c5d7ea'
    }
    : readinessTier === 'low' ? {
      text: '#475569',
      bg: '#f3f4f8',
      border: '#cbd5e1'
    }
    : {
      text: '#5f7690',
      bg: '#f8fafd',
      border: '#dce5f1'
    };
</script>

<section class="hero">
  <div class="hero-content">
    <div>
      <h2>Daily Dashboard</h2>
      <p class="hero-sub">Your morning readiness and personalized advice.</p>
    </div>
    <div class="sync-actions">
      {#if lastSyncDate}
        <span class="sync-meta">Garmin: {lastSyncDate}</span>
      {/if}
      <button class="btn-refresh" on:click={load} disabled={isLoading} aria-label="Refresh latest metrics" title="Refresh metrics">
        <svg class="refresh-icon {isLoading ? 'spin' : ''}" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        <span>{isLoading ? 'Syncing...' : 'Refresh'}</span>
      </button>
    </div>
  </div>
</section>

{#if isLoading}
  <section class="card skeleton-card" aria-busy="true" aria-label="Loading readiness and health metrics">
    <div class="skeleton-shimmer skeleton-label"></div>
    <div class="skeleton-shimmer skeleton-score"></div>
    <div class="skeleton-shimmer skeleton-status"></div>
  </section>

  <section class="card skeleton-card" aria-busy="true">
    <div class="skeleton-shimmer skeleton-title"></div>
    <div class="skeleton-shimmer skeleton-text"></div>
  </section>

  <section class="card skeleton-snap" aria-busy="true">
    <div class="skeleton-shimmer skeleton-pill"></div>
    <div class="skeleton-shimmer skeleton-pill"></div>
    <div class="skeleton-shimmer skeleton-pill"></div>
    <div class="skeleton-shimmer skeleton-pill"></div>
  </section>
{:else if loadError}
  <section class="card error-card" role="alert">
    <div class="error-header">
      <span class="error-icon" aria-hidden="true">ℹ️</span>
      <h3>Unable to load latest metrics</h3>
    </div>
    <p>{adviceMessage}</p>
    <div class="error-actions">
      <button class="btn-retry" on:click={load}>Try Again</button>
    </div>
  </section>
{:else}
  {#if readinessScore !== null}
    <section
      class="card readiness-card"
      style="border-color: {readinessTheme.border}; background-color: {readinessTheme.bg};"
      aria-label="Today's readiness score: {readinessScore} percent, {readinessStatus}"
    >
      <div class="readiness-header">
        <span class="readiness-label" style="color: {readinessTheme.text};">Today's Readiness</span>
      </div>
      <div class="readiness-value" style="color: {readinessTheme.text};">
        {readinessScore}<small>%</small>
      </div>
      <div class="readiness-status" style="color: {readinessTheme.text};">
        {readinessStatus}
      </div>
    </section>
  {/if}

  <section class="card advice-card" aria-live="polite">
    <h3>Predictive Advice</h3>
    <p>{adviceMessage}</p>
  </section>

  {#if latestSleep || latestBattery || latestHrv || latestStress}
    <section class="card garmin-snap" aria-label="Morning Biometric Snapshot">
      <span class="snap-label">Morning Snapshot</span>
      {#if latestSleep}
        <span class="snap-pill">Sleep {fmtMinutes(latestSleep.total_sleep_minutes)} · {latestSleep.sleep_score ?? '-'}/100</span>
      {/if}
      {#if latestBattery}
        <span class="snap-pill">Body Battery AM {latestBattery.morning_value ?? '-'}</span>
      {/if}
      {#if latestHrv}
        <span class="snap-pill">HRV {latestHrv.weekly_avg ?? '-'}ms</span>
      {/if}
      {#if latestStress}
        <span class="snap-pill">Stress {latestStress.overall_stress_level ?? '-'}</span>
      {/if}
    </section>
  {:else if !latestSleep && !latestBattery && !latestHrv && !latestStress}
    <section class="card empty-snap">
      <span class="empty-text">No Garmin metrics recorded for today yet. Data will appear automatically following your next watch sync.</span>
    </section>
  {/if}
{/if}

<div class="dashboard-action">
  <a href="/mood-entry" class="btn-cta">
    Log Today's Mood & Activities
  </a>
</div>

<style>
  .hero-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
  }
  .hero-sub {
    margin: 0.25rem 0 0 0;
    color: var(--color-neutral-text-muted, #496685);
    font-size: 0.92rem;
  }
  .sync-actions {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  .sync-meta {
    font-size: 0.82rem;
    color: var(--color-neutral-text-muted, #496685);
    background: #edf4fc;
    padding: 0.2rem 0.55rem;
    border-radius: 6px;
    border: 1px solid #d2e3f5;
  }
  .btn-refresh {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    background: #ffffff;
    border: 1px solid var(--color-neutral-border, #d9e2ef);
    color: var(--color-neutral-text, #132238);
    font-size: 0.84rem;
    font-weight: 500;
    padding: 0.28rem 0.65rem;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .btn-refresh:hover:not(:disabled) {
    background: #f4f8fd;
    border-color: #bcd3eb;
  }
  .refresh-icon.spin {
    animation: rotate 1s linear infinite;
  }
  @keyframes rotate {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  .readiness-card {
    text-align: center;
    border: 1px solid;
    border-radius: 12px;
    padding: 1.5rem 1rem;
    margin-bottom: 1rem;
    transition: background-color 0.2s ease, border-color 0.2s ease;
  }
  .readiness-header {
    margin-bottom: 0.4rem;
  }
  .readiness-label {
    font-size: 0.88rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .readiness-value {
    font-size: 3rem;
    font-weight: 700;
    line-height: 1.1;
    letter-spacing: -0.02em;
  }
  .readiness-value small {
    font-size: 1.5rem;
    font-weight: 500;
    margin-left: 2px;
  }
  .readiness-status {
    margin-top: 0.4rem;
    font-size: 0.95rem;
    font-weight: 500;
  }

  .advice-card {
    background: #f7fafd;
    border: 1px solid #dce7f4;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    margin-bottom: 1rem;
  }
  .advice-card h3 {
    margin-top: 0;
    margin-bottom: 0.45rem;
    color: #1e4b76;
    font-size: 1.05rem;
    font-weight: 600;
  }
  .advice-card p {
    margin: 0;
    color: #496685;
    line-height: 1.45;
    font-size: 0.95rem;
  }

  .garmin-snap {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    background: #ffffff;
    border: 1px solid var(--color-neutral-border, #d9e2ef);
    border-radius: 12px;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
  }
  .snap-label {
    font-size: 0.78rem;
    font-weight: 700;
    color: #496685;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-right: 0.25rem;
  }
  .snap-pill {
    background: #eef4fb;
    border: 1px solid #ccddf4;
    border-radius: 999px;
    padding: 0.25rem 0.65rem;
    font-size: 0.82rem;
    color: #1e4b76;
    font-weight: 500;
  }

  .empty-snap {
    background: #f8fafd;
    border: 1px dashed #d5e2f1;
    border-radius: 12px;
    padding: 0.9rem 1rem;
    margin-bottom: 1rem;
    color: #5c7899;
    font-size: 0.9rem;
    text-align: center;
  }

  /* Skeleton Loading Styles */
  .skeleton-card {
    background: #ffffff;
    border: 1px solid #e5edf7;
    border-radius: 12px;
    padding: 1.5rem 1rem;
    margin-bottom: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.6rem;
  }
  .skeleton-snap {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    background: #ffffff;
    border: 1px solid #e5edf7;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    margin-bottom: 1rem;
  }
  .skeleton-shimmer {
    background: linear-gradient(90deg, #f0f4fa 25%, #e6edf6 50%, #f0f4fa 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 6px;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  .skeleton-label { width: 140px; height: 16px; }
  .skeleton-score { width: 90px; height: 48px; border-radius: 8px; margin: 0.3rem 0; }
  .skeleton-status { width: 200px; height: 18px; }
  .skeleton-title { width: 150px; height: 18px; align-self: flex-start; }
  .skeleton-text { width: 90%; height: 28px; align-self: flex-start; }
  .skeleton-pill { width: 110px; height: 26px; border-radius: 999px; }

  /* Error Recovery Card */
  .error-card {
    background: #fdfaf7;
    border: 1px solid #eedfd4;
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 1rem;
  }
  .error-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.4rem;
  }
  .error-header h3 {
    margin: 0;
    font-size: 1rem;
    color: #8c5225;
  }
  .error-card p {
    margin: 0 0 0.8rem 0;
    color: #634731;
    font-size: 0.9rem;
  }
  .btn-retry {
    background: #ffffff;
    border: 1px solid #c9b09d;
    color: #634731;
    font-size: 0.86rem;
    font-weight: 600;
    padding: 0.35rem 0.8rem;
    border-radius: 8px;
    cursor: pointer;
  }
  .btn-retry:hover {
    background: #f9f3ee;
  }

  /* Call-to-Action conforming to DESIGN.md */
  .dashboard-action {
    margin-top: 1.5rem;
    margin-bottom: 2rem;
    display: flex;
    justify-content: center;
  }
  .btn-cta {
    background: var(--color-primary, #dceeff);
    color: var(--color-primary-content, #173a5c);
    border: 1px solid var(--color-primary-border, #9ec0e7);
    border-radius: 10px;
    padding: 0.75rem 2rem;
    font-size: 1.05rem;
    font-weight: 600;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: none;
    min-height: 44px; /* Accessible touch target */
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .btn-cta:hover {
    background: #cde4fa;
    border-color: #8bb4e1;
  }
  .btn-cta:focus-visible {
    outline: 2px solid #5b9bd5;
    outline-offset: 2px;
  }
</style>
