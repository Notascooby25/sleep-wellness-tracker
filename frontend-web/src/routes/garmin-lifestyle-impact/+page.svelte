<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';

  type ImpactItem = {
    activity: string;
    delta: number;
    sample_size: number;
    highest: boolean;
  };

  type ImpactResponse = {
    metric: 'sleep_score' | 'overnight_hrv' | 'overnight_stress';
    period_label: string;
    avg_value: number | null;
    positive_impact: ImpactItem[];
    negative_impact: ImpactItem[];
    minimal_impact: ImpactItem[];
    threshold: number | null;
    sample_days: number;
  };

  const periodOptions = [
    { label: '7d', days: 7 },
    { label: '4w', days: 28 },
    { label: '12w', days: 84 }
  ];

  const metricOptions = [
    { value: 'overnight_stress', label: 'Overnight Stress' },
    { value: 'overnight_hrv', label: 'Overnight HRV' },
    { value: 'sleep_score', label: 'Sleep Score' }
  ] as const;

  let selectedDays = 28;
  let selectedMetric: ImpactResponse['metric'] = 'sleep_score';
  let busy = false;
  let status = '';
  let data: ImpactResponse | null = null;

  const metricLabel = (metric: ImpactResponse['metric']) => {
    const found = metricOptions.find((item) => item.value === metric);
    return found ? found.label : metric;
  };

  const fmtDelta = (delta: number) => `${delta > 0 ? '+' : ''}${delta.toFixed(2)}`;

  const tooltip = (item: ImpactItem) => {
    const metricName = metricLabel(selectedMetric).toLowerCase();
    return `On days you logged ${item.activity}, your ${metricName} averaged ${fmtDelta(item.delta)} versus baseline.`;
  };

  const load = async () => {
    busy = true;
    status = '';
    try {
      data = await getJson<ImpactResponse>(`/lifestyle-impact?metric=${selectedMetric}&days=${selectedDays}`);
    } catch (error) {
      status = `Load failed: ${error}`;
      data = null;
    } finally {
      busy = false;
    }
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Lifestyle Impact</h2>
  <p>See which logged activities trend with better or worse Garmin wellness outcomes in your selected period.</p>
</section>

<section class="card controls">
  <div class="period-tabs">
    {#each periodOptions as option}
      <button
        class="tab"
        class:active={selectedDays === option.days}
        on:click={() => {
          selectedDays = option.days;
          load();
        }}
      >{option.label}</button>
    {/each}
  </div>

  <div class="metric-tabs">
    {#each metricOptions as option}
      <button
        class="tab"
        class:active={selectedMetric === option.value}
        on:click={() => {
          selectedMetric = option.value;
          load();
        }}
      >{option.label}</button>
    {/each}
  </div>

  {#if data}
    <div class="period-label">{data.period_label}</div>
    <div class="avg-card">
      <div class="avg-value">{data.avg_value ?? '-'}</div>
      <div class="avg-label">Average {metricLabel(data.metric)}</div>
    </div>
  {/if}

  {#if busy}
    <p class="status-msg">Loading impact analysis...</p>
  {:else if status}
    <p class="status-msg error">{status}</p>
  {/if}
</section>

{#if data}
  <section class="impact-grid">
    <article class="card impact-card">
      <h3>Positive Impact</h3>
      {#if data.positive_impact.length === 0}
        <p class="empty">No activities met the positive threshold.</p>
      {:else}
        {#each data.positive_impact as item}
          <div class="impact-row">
            <div>
              <div class="activity-name">{item.activity}</div>
              <div class="activity-delta">{fmtDelta(item.delta)} ({item.sample_size} days)</div>
            </div>
            <div class="row-end">
              {#if item.highest}<span class="badge">Highest Impact</span>{/if}
              <span class="info" title={tooltip(item)}>i</span>
            </div>
          </div>
        {/each}
      {/if}
    </article>

    <article class="card impact-card">
      <h3>Negative Impact</h3>
      {#if data.negative_impact.length === 0}
        <p class="empty">No activities met the negative threshold.</p>
      {:else}
        {#each data.negative_impact as item}
          <div class="impact-row">
            <div>
              <div class="activity-name">{item.activity}</div>
              <div class="activity-delta">{fmtDelta(item.delta)} ({item.sample_size} days)</div>
            </div>
            <div class="row-end">
              {#if item.highest}<span class="badge">Highest Impact</span>{/if}
              <span class="info" title={tooltip(item)}>i</span>
            </div>
          </div>
        {/each}
      {/if}
    </article>

    <article class="card impact-card">
      <h3>Minimal Impact</h3>
      {#if data.minimal_impact.length === 0}
        <p class="empty">No activities met the minimum sample threshold.</p>
      {:else}
        {#each data.minimal_impact as item}
          <div class="impact-row">
            <div>
              <div class="activity-name">{item.activity}</div>
              <div class="activity-delta">{fmtDelta(item.delta)} ({item.sample_size} days)</div>
            </div>
            <div class="row-end">
              {#if item.highest}<span class="badge">Highest Impact</span>{/if}
              <span class="info" title={tooltip(item)}>i</span>
            </div>
          </div>
        {/each}
      {/if}
    </article>
  </section>
{/if}

<style>
  .controls { padding: 1rem; }
  .period-tabs,
  .metric-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.7rem;
  }
  .tab {
    border-radius: 999px;
    background: #edf4fd;
    border: 1px solid #cadcef;
    color: #1e4b76;
    font-size: 0.84rem;
    padding: 0.3rem 0.7rem;
  }
  .tab.active {
    background: #d4e9ff;
    border-color: #a9c9ea;
    font-weight: 700;
  }
  .period-label {
    font-size: 0.84rem;
    color: #496685;
    margin-bottom: 0.55rem;
  }
  .avg-card {
    border: 1px solid #d9e2ef;
    border-radius: 12px;
    background: #f8fbff;
    padding: 0.8rem;
    display: inline-block;
  }
  .avg-value {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    color: #173a5c;
  }
  .avg-label {
    margin-top: 0.25rem;
    color: #496685;
    font-size: 0.9rem;
  }
  .status-msg {
    margin-top: 0.65rem;
    font-size: 0.9rem;
    background: #d4edda;
    color: #22543d;
    border-radius: 8px;
    padding: 0.35rem 0.6rem;
  }
  .status-msg.error {
    background: #fce8e8;
    color: #8a1c1c;
  }

  .impact-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    margin-top: 0.8rem;
  }
  .impact-card h3 {
    margin: 0 0 0.55rem;
    color: #163c61;
  }
  .impact-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    border-top: 1px solid #e5edf8;
    padding: 0.45rem 0;
  }
  .impact-row:first-of-type {
    border-top: none;
    padding-top: 0;
  }
  .activity-name {
    font-size: 0.9rem;
    font-weight: 700;
    color: #163c61;
  }
  .activity-delta {
    font-size: 0.8rem;
    color: #496685;
  }
  .row-end {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }
  .badge {
    border-radius: 999px;
    border: 1px solid #c3d8f1;
    background: #ecf5ff;
    color: #1d4b76;
    padding: 0.1rem 0.45rem;
    font-size: 0.72rem;
    font-weight: 700;
    white-space: nowrap;
  }
  .info {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: #edf4fd;
    border: 1px solid #cadcef;
    color: #1e4b76;
    font-size: 0.74rem;
    font-weight: 700;
    cursor: help;
  }
  .empty {
    margin: 0;
    color: #8091a7;
    font-size: 0.88rem;
  }

  @media (max-width: 960px) {
    .impact-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
