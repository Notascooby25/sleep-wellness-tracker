<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, putJson } from '$lib/api';

  type Metric = 'sleep_score' | 'overnight_hrv' | 'overnight_stress' | 'resting_heart_rate' | 'steps';
  type Confidence = 'strong' | 'some' | 'weak';

  type ImpactItem = {
    activity_id: number | null;
    activity: string;
    effect: number;
    with_nights: number;
    without_nights: number;
    confidence: Confidence;
    better: boolean;
    logged_with: string[];
  };

  type TooEarlyItem = { activity_id: number | null; activity: string; with_nights: number };
  type LeftOutItem = { activity_id: number; activity: string; reason: string };

  type ImpactResponse = {
    metric: Metric;
    metric_label: string;
    higher_is_better: boolean;
    period_label: string;
    avg_value: number | null;
    nights_analysed: number;
    items: ImpactItem[];
    too_early: TooEarlyItem[];
    left_out: LeftOutItem[];
    min_nights: number;
  };

  type ActivityRecord = { id: number; hidden_pages: string[] | null };

  const PAGE_KEY = 'lifestyle_impact';

  const periodOptions = [
    { label: '4w', days: 28 },
    { label: '12w', days: 84 },
    { label: '26w', days: 182 }
  ];

  const metricOptions: { value: Metric; label: string }[] = [
    { value: 'overnight_stress', label: 'Overnight Stress' },
    { value: 'overnight_hrv', label: 'Overnight HRV' },
    { value: 'sleep_score', label: 'Sleep Score' },
    { value: 'resting_heart_rate', label: 'Resting Heart Rate' },
    { value: 'steps', label: 'Steps' }
  ];

  const units: Record<Metric, string> = {
    sleep_score: 'points',
    overnight_hrv: 'ms',
    overnight_stress: '',
    resting_heart_rate: 'bpm',
    steps: 'steps'
  };

  const confidenceWords: Record<Confidence, string> = {
    strong: 'Strong',
    some: 'Some evidence',
    weak: 'Weak'
  };

  const confidenceBars: Record<Confidence, number> = { strong: 3, some: 2, weak: 1 };

  const reasonWords: Record<string, string> = {
    habit: 'just a habit',
    describes_night: 'describes the night',
    reaction: 'because of a symptom',
    symptom: 'a symptom',
    hidden: 'hidden here'
  };

  const roleChoices = [
    { label: 'Just a habit I’m recording', hint: 'Leave it out of all impact and trigger reports', role: 'habit' },
    { label: 'Describes how the night went', hint: 'An outcome, like “Woke During Night”, not a cause', role: 'describes_night' },
    { label: 'Something I do because of a symptom', hint: 'Never shown as a cause or trigger', role: 'reaction' },
    { label: 'Hide from this page only', hint: 'Keep it in every other report', role: null }
  ];

  let selectedDays = 28;
  let selectedMetric: Metric = 'sleep_score';
  let busy = false;
  let status = '';
  let data: ImpactResponse | null = null;
  let openMenuId: number | null = null;
  let savingId: number | null = null;

  const fmtEffect = (effect: number, metric: Metric) => {
    const size = Math.abs(effect).toLocaleString('en-GB', { maximumFractionDigits: 1 });
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    const unit = units[metric];
    return unit ? `${sign}${size} ${unit}` : `${sign}${size}`;
  };

  const fmtAverage = (value: number | null, metric: Metric) =>
    value === null ? '–' : value.toLocaleString('en-GB', { maximumFractionDigits: metric === 'steps' ? 0 : 1 });

  const rowKey = (item: { activity_id: number | null; activity: string }) =>
    `${item.activity_id ?? 'watch'}:${item.activity}`;

  const nights = (n: number) => `${n} ${n === 1 ? 'night' : 'nights'}`;

  const load = async () => {
    busy = true;
    status = '';
    openMenuId = null;
    try {
      data = await getJson<ImpactResponse>(`/lifestyle-impact?metric=${selectedMetric}&days=${selectedDays}`);
    } catch (error) {
      status = `Couldn’t load the results: ${error}`;
      data = null;
    } finally {
      busy = false;
    }
  };

  const saveSettings = async (activityId: number, body: Record<string, unknown>) => {
    savingId = activityId;
    status = '';
    try {
      await putJson(`/activities/${activityId}/report-settings`, body);
      await load();
    } catch (error) {
      status = `Couldn’t save that change: ${error}`;
    } finally {
      savingId = null;
    }
  };

  const hiddenPagesFor = async (activityId: number) => {
    const record = await getJson<ActivityRecord>(`/activities/${activityId}`);
    return record.hidden_pages ?? [];
  };

  const chooseRole = async (activityId: number, role: string | null) => {
    if (role) {
      await saveSettings(activityId, { report_role: role });
      return;
    }
    try {
      const pages = await hiddenPagesFor(activityId);
      await saveSettings(activityId, { hidden_pages: [...new Set([...pages, PAGE_KEY])] });
    } catch (error) {
      status = `Couldn’t save that change: ${error}`;
    }
  };

  const bringBack = async (item: LeftOutItem) => {
    if (item.reason !== 'hidden') {
      await saveSettings(item.activity_id, { report_role: null });
      return;
    }
    try {
      const pages = await hiddenPagesFor(item.activity_id);
      await saveSettings(item.activity_id, { hidden_pages: pages.filter((page) => page !== PAGE_KEY) });
    } catch (error) {
      status = `Couldn’t save that change: ${error}`;
    }
  };

  const toggleMenu = (activityId: number) => {
    openMenuId = openMenuId === activityId ? null : activityId;
  };

  onMount(load);
</script>

<section class="hero">
  <h2>Lifestyle Impact</h2>
  <p>What seems to change your sleep and recovery, worked out from your own nights.</p>
</section>

<section class="card controls">
  <div class="tab-row" role="group" aria-label="Period">
    {#each periodOptions as option}
      <button
        class="tab"
        class:active={selectedDays === option.days}
        aria-pressed={selectedDays === option.days}
        on:click={() => {
          selectedDays = option.days;
          load();
        }}
      >{option.label}</button>
    {/each}
  </div>

  <div class="tab-row" role="group" aria-label="Measure">
    {#each metricOptions as option}
      <button
        class="tab"
        class:active={selectedMetric === option.value}
        aria-pressed={selectedMetric === option.value}
        on:click={() => {
          selectedMetric = option.value;
          load();
        }}
      >{option.label}</button>
    {/each}
  </div>

  {#if data}
    <div class="summary">
      <span class="avg-value">{fmtAverage(data.avg_value, data.metric)}</span>
      <span class="avg-label">average {data.metric_label.toLowerCase()} · {data.period_label} · {nights(data.nights_analysed)}</span>
    </div>
  {/if}

  {#if status}
    <p class="status-msg" role="alert">{status}</p>
  {/if}
</section>

<section class="card results" aria-busy={busy}>
  <h3>What seems to affect your {(data?.metric_label ?? 'sleep score').toLowerCase()}</h3>

  {#if busy && !data}
    <ul class="impact-list" aria-hidden="true">
      {#each [0, 1, 2] as _}
        <li class="impact-row skeleton"><span class="skeleton-bar wide"></span><span class="skeleton-bar"></span></li>
      {/each}
    </ul>
  {:else if data}
    {#if data.items.length === 0}
      <p class="empty">
        Nothing stands out yet. An item shows up here once it has at least {data.min_nights} nights with it and
        {data.min_nights} without, and makes a real difference. Try a longer period.
      </p>
    {:else}
      <ul class="impact-list" class:dimmed={busy}>
        {#each data.items as item (rowKey(item))}
          <li class="impact-row">
            <div class="row-main">
              <div class="row-text">
                <div class="activity-name">{item.activity}</div>
                <div class="activity-detail">
                  <span class="effect" class:better={item.better} class:worse={!item.better}>
                    {fmtEffect(item.effect, data.metric)}
                  </span>
                  <span class="nights">· {nights(item.with_nights)} with, {item.without_nights} without</span>
                </div>
                {#if item.logged_with.length}
                  <div class="twin-note">Always logged with {item.logged_with.join(', ')}, so the app can’t separate them.</div>
                {/if}
              </div>

              <div class="row-end">
                <span class="confidence" aria-label={`Confidence: ${confidenceWords[item.confidence]}`}>
                  <span class="meter" aria-hidden="true">
                    {#each [1, 2, 3] as bar}
                      <i class:on={bar <= confidenceBars[item.confidence]}></i>
                    {/each}
                  </span>
                  <span class="confidence-word">{confidenceWords[item.confidence]}</span>
                </span>
                {#if item.activity_id !== null}
                  {@const id = item.activity_id}
                  <button
                    class="menu-button"
                    aria-label={`Change how ${item.activity} is used`}
                    aria-expanded={openMenuId === id}
                    disabled={savingId !== null}
                    on:click={() => toggleMenu(id)}
                  >
                    <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                      <circle cx="4.5" cy="10" r="1.6" /><circle cx="10" cy="10" r="1.6" /><circle cx="15.5" cy="10" r="1.6" />
                    </svg>
                  </button>
                {:else}
                  <span class="menu-spacer" title="Recorded by your watch, so its role can’t be changed"></span>
                {/if}
              </div>
            </div>

            {#if item.activity_id !== null && openMenuId === item.activity_id}
              {@const id = item.activity_id}
              <div class="role-menu">
                <p class="role-question">What is “{item.activity}” for you?</p>
                {#each roleChoices as choice}
                  <button class="role-choice" disabled={savingId !== null} on:click={() => chooseRole(id, choice.role)}>
                    <span class="choice-label">{choice.label}</span>
                    <span class="choice-hint">{choice.hint}</span>
                  </button>
                {/each}
                <button class="role-cancel" on:click={() => (openMenuId = null)}>Cancel</button>
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if data.too_early.length}
      <h4>Too early to tell</h4>
      <ul class="early-list">
        {#each data.too_early as item (rowKey(item))}
          <li>
            <span class="early-name">{item.activity}</span>
            <span class="early-count">{nights(item.with_nights)} so far, needs at least {data.min_nights}</span>
          </li>
        {/each}
      </ul>
    {/if}

    {#if data.left_out.length}
      <h4>Left out of this page</h4>
      <ul class="chip-list">
        {#each data.left_out as item (item.activity_id)}
          <li class="chip">
            <span>{item.activity} · {reasonWords[item.reason] ?? item.reason}</span>
            <button
              class="chip-remove"
              aria-label={`Bring ${item.activity} back`}
              disabled={savingId !== null}
              on:click={() => bringBack(item)}
            >
              <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>
          </li>
        {/each}
      </ul>
    {/if}

    <p class="footnote">
      The list is ordered by how sure the app is, then by size. Confidence is how rarely a gap this big turns up
      when your nights are shuffled at random. During Sleep and Morning items describe the night, so they aren’t
      listed here.
    </p>
  {/if}
</section>

<style>
  .controls {
    padding: 14px 16px;
  }
  .tab-row {
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
    padding: 0.3rem 0.75rem;
    transition: background-color 160ms ease-out, border-color 160ms ease-out;
  }
  .tab:hover {
    background: #e2eefc;
  }
  .tab.active {
    background: var(--color-primary);
    border-color: var(--color-primary-border);
    font-weight: 700;
  }
  .summary {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.25rem 0.6rem;
    margin-top: 0.2rem;
  }
  .avg-value {
    font-size: 1.9rem;
    font-weight: 700;
    line-height: 1;
    color: var(--color-primary-content);
    font-variant-numeric: tabular-nums;
  }
  .avg-label {
    color: var(--color-neutral-text-muted);
    font-size: 0.86rem;
  }
  .status-msg {
    margin: 0.7rem 0 0;
    font-size: 0.9rem;
    background: #fce8e8;
    color: #8a1c1c;
    border-radius: 10px;
    padding: 0.4rem 0.65rem;
  }

  .results {
    padding: 14px 16px;
  }
  .results h3 {
    margin: 0 0 0.4rem;
    color: var(--color-primary-content);
    font-size: 1.05rem;
  }
  .results h4 {
    margin: 1.4rem 0 0.4rem;
    color: var(--color-neutral-text-muted);
    font-size: 0.86rem;
    font-weight: 600;
  }

  .impact-list,
  .early-list,
  .chip-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .impact-list.dimmed {
    opacity: 0.55;
    transition: opacity 160ms ease-out;
  }
  .impact-row {
    border-top: 1px solid #e5edf8;
    padding: 0.7rem 0;
  }
  .impact-row:first-child {
    border-top: none;
  }
  .row-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }
  .row-text {
    min-width: 0;
  }
  .activity-name {
    font-weight: 700;
    color: var(--color-neutral-text);
  }
  .activity-detail {
    margin-top: 0.15rem;
    font-size: 0.86rem;
    color: var(--color-neutral-text-muted);
    font-variant-numeric: tabular-nums;
  }
  .effect {
    font-weight: 700;
  }
  .effect.better {
    color: var(--color-better);
  }
  .effect.worse {
    color: var(--color-worse);
  }
  .twin-note {
    margin-top: 0.2rem;
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
  }

  .row-end {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-shrink: 0;
  }
  .confidence {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
  }
  .meter {
    display: inline-flex;
    gap: 3px;
  }
  .meter i {
    display: block;
    width: 15px;
    height: 7px;
    border-radius: 999px;
    background: var(--color-confidence-off);
  }
  .meter i.on {
    background: var(--color-confidence);
  }
  .confidence-word {
    min-width: 6.6em;
  }
  .menu-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 10px;
    background: #edf4fd;
    border: 1px solid #cadcef;
    fill: #1e4b76;
    transition: background-color 160ms ease-out;
  }
  .menu-button:hover:not(:disabled),
  .menu-button[aria-expanded='true'] {
    background: var(--color-primary);
    border-color: var(--color-primary-border);
  }
  .menu-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .menu-spacer {
    display: inline-block;
    width: 32px;
  }

  .role-menu {
    margin-top: 0.6rem;
    padding: 0.6rem;
    border: 1px solid #cadcef;
    border-radius: 12px;
    background: #f6faff;
    display: grid;
    gap: 0.3rem;
  }
  .role-question {
    margin: 0 0 0.2rem;
    font-size: 0.86rem;
    color: var(--color-neutral-text-muted);
  }
  .role-choice {
    display: grid;
    gap: 0.1rem;
    text-align: left;
    padding: 0.5rem 0.6rem;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--color-neutral-text);
    transition: background-color 160ms ease-out;
  }
  .role-choice:hover:not(:disabled) {
    background: #e6f0fb;
    border-color: #cadcef;
  }
  .role-choice:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .choice-label {
    font-weight: 600;
  }
  .choice-hint {
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
  }
  .role-cancel {
    justify-self: start;
    margin-top: 0.2rem;
    padding: 0.35rem 0.7rem;
    border-radius: 10px;
    border: 1px solid #cadcef;
    background: #fff;
    color: #1e4b76;
    font-size: 0.84rem;
  }

  .early-list li {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.2rem 0.75rem;
    padding: 0.4rem 0;
    border-top: 1px solid #edf2f9;
    font-size: 0.9rem;
  }
  .early-list li:first-child {
    border-top: none;
  }
  .early-name {
    color: var(--color-neutral-text-muted);
    font-weight: 600;
  }
  .early-count {
    color: var(--color-neutral-text-muted);
    font-size: 0.84rem;
    font-variant-numeric: tabular-nums;
  }

  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border-radius: 999px;
    border: 1px solid #c3d8f1;
    background: #ecf5ff;
    color: #1d4b76;
    padding: 0.15rem 0.2rem 0.15rem 0.65rem;
    font-size: 0.82rem;
  }
  .chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    border-radius: 999px;
    border: none;
    background: transparent;
    stroke: #1d4b76;
    stroke-width: 1.8;
    stroke-linecap: round;
  }
  .chip-remove:hover:not(:disabled) {
    background: #d8e9fc;
  }

  .empty,
  .footnote {
    color: var(--color-neutral-text-muted);
    font-size: 0.86rem;
    max-width: 70ch;
  }
  .empty {
    margin: 0.4rem 0 0;
  }
  .footnote {
    margin: 1.4rem 0 0;
    line-height: 1.5;
  }

  .skeleton {
    display: grid;
    gap: 0.4rem;
  }
  .skeleton-bar {
    display: block;
    height: 0.8rem;
    width: 30%;
    border-radius: 999px;
    background: linear-gradient(90deg, #f0f4fa 25%, #e6edf6 50%, #f0f4fa 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
  }
  .skeleton-bar.wide {
    width: 45%;
  }
  @keyframes shimmer {
    from { background-position: 200% 0; }
    to { background-position: -200% 0; }
  }
  @media (prefers-reduced-motion: reduce) {
    .skeleton-bar { animation: none; }
  }

  @media (max-width: 560px) {
    .row-main {
      align-items: flex-start;
    }
    .confidence-word {
      display: none;
    }
    .confidence {
      padding-top: 0.35rem;
    }
  }
</style>
