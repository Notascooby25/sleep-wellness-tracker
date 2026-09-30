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

  const fmtMinutes = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${Math.floor(value / 60)}h ${String(value % 60).padStart(2, '0')}m`;
  };

  const load = async () => {
    loadError = false;
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
    } catch (error) {
      adviceMessage = "Unable to load advice right now.";
      loadError = true;
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

  $: readinessColor = readinessScore === null ? '#8091a7'
    : readinessScore >= 70 ? '#086c3a'
    : readinessScore >= 50 ? '#854d0e'
    : '#b42318';

  $: readinessBg = readinessScore === null ? '#e8f0f9'
    : readinessScore >= 70 ? '#dcfae6'
    : readinessScore >= 50 ? '#fef3c7'
    : '#fee4e2';
</script>

<section class="hero">
  <h2>Daily Dashboard</h2>
  <p>Your morning readiness and personalized advice.</p>
</section>

{#if readinessScore !== null}
<section class="card readiness-card" style="border-color:{readinessColor}; background-color:{readinessBg};">
  <div class="readiness-label" style="color:{readinessColor};">Today's Readiness</div>
  <div class="readiness-value" style="color:{readinessColor};">{readinessScore}<small>%</small></div>
</section>
{/if}

<section class="card advice-card">
  <h3>Predictive Advice</h3>
  <p>{adviceMessage}</p>
</section>

{#if latestSleep || latestBattery || latestHrv || latestStress}
<section class="card garmin-snap">
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
{/if}

<div style="margin-top: 1.5rem; display: flex; justify-content: center;">
  <a href="/mood-entry" class="btn-primary" style="text-decoration: none; display: inline-block; padding: 0.8rem 2rem; font-size: 1.1rem; border-radius: 999px;">
    Log Today's Mood & Activities
  </a>
</div>

<style>
  .readiness-card {
    text-align: center;
    border: 2px solid;
    padding: 2rem 1rem;
    margin-bottom: 1rem;
  }
  .readiness-label {
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
  }
  .readiness-value {
    font-size: 4.5rem;
    font-weight: 800;
    line-height: 1;
  }
  .readiness-value small {
    font-size: 2rem;
  }
  .advice-card {
    background: #f7fafd;
    border: 1px solid #dce7f4;
    margin-bottom: 1rem;
  }
  .advice-card h3 {
    margin-top: 0;
    margin-bottom: 0.5rem;
    color: #1e4b76;
    font-size: 1.1rem;
  }
  .advice-card p {
    margin: 0;
    color: #496685;
    line-height: 1.4;
    font-size: 0.95rem;
  }
  .garmin-snap { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .snap-label { font-size: 0.78rem; font-weight: 700; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; }
  .snap-pill { background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.18rem 0.55rem; font-size: 0.8rem; color: #1e4b76; }
  .btn-primary { background: #3c79c5; color: #fff; border-color: #3168ad; }
</style>
