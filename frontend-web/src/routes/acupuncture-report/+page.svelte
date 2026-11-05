<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, putJson } from '$lib/api';

  type Confidence = 'strong' | 'some' | 'weak';

  type TriggerItem = {
    activity_id: number | null;
    activity: string;
    effect: number;
    with_nights: number;
    without_nights: number;
    confidence: Confidence;
    better: boolean;
    source?: 'activity' | 'garmin';
    logged_with: string[];
  };

  type BiometricItem = {
    metric: string;
    symptom_avg: number;
    clean_avg: number;
    effect: number;
    unit: string;
    confidence: Confidence;
    better: boolean;
  };

  type TooEarlyItem = { activity_id: number | null; activity: string; with_nights: number };
  type LeftOutItem = { activity_id: number; activity: string; reason: string };

  type HeadacheSummaryResponse = {
    start_date: string | null;
    end_date: string | null;
    total_days: number;
    symptom_days: number;
    clean_days: number;
    frequency: number;
    average_severity: number | null;
    triggers_day_before: TriggerItem[];
    triggers_same_day: TriggerItem[];
    biometrics: BiometricItem[];
    too_early: TooEarlyItem[];
    left_out: LeftOutItem[];
    min_nights: number;
  };

  type ActivityRecord = { id: number; hidden_pages: string[] | null };

  const PAGE_KEY = 'acupuncture_report';

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

  let sessions: string[] = [];
  let startDate: string = '';
  let endDate: string = '';

  let summary: HeadacheSummaryResponse | null = null;
  let loading = true;
  let error = '';
  let status = '';
  let openMenuId: number | null = null;
  let savingId: number | null = null;

  const fmtRiskEffect = (effect: number) => {
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    return `${sign}${Math.abs(effect)}% headache risk`;
  };

  const fmtFrequencyEffect = (effect: number) => {
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    return `${sign}${Math.abs(effect)}% frequency`;
  };

  const fmtBioDiff = (effect: number, unit: string) => {
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    const val = Math.abs(effect).toLocaleString('en-GB', { maximumFractionDigits: 1 });
    return unit ? `${sign}${val} ${unit}` : `${sign}${val}`;
  };

  const daysLabel = (n: number) => `${n} ${n === 1 ? 'day' : 'days'}`;

  const loadInitial = async () => {
    try {
      const sessRes = await getJson<{ sessions: string[] }>('/reports/acupuncture-sessions');
      sessions = sessRes?.sessions || [];

      if (sessions.length > 0) {
        const lastSession = new Date(sessions[0]);
        lastSession.setDate(lastSession.getDate() + 1);
        startDate = lastSession.toISOString().slice(0, 10);
        endDate = new Date().toISOString().slice(0, 10);
      } else {
        const d = new Date();
        d.setDate(d.getDate() - 30);
        startDate = d.toISOString().slice(0, 10);
        endDate = new Date().toISOString().slice(0, 10);
      }
      await loadSummary();
    } catch (err) {
      error = 'Failed to load initial data.';
      loading = false;
    }
  };

  const loadSummary = async () => {
    loading = true;
    error = '';
    openMenuId = null;
    try {
      const query = `?start_date=${startDate}&end_date=${endDate}`;
      summary = await getJson<HeadacheSummaryResponse>(`/reports/headache-summary${query}`);
    } catch (err) {
      error = 'Failed to load summary.';
      summary = null;
    } finally {
      loading = false;
    }
  };

  const saveSettings = async (activityId: number, body: Record<string, unknown>) => {
    savingId = activityId;
    status = '';
    try {
      await putJson(`/activities/${activityId}/report-settings`, body);
      await loadSummary();
    } catch (err) {
      status = `Couldn’t save that change: ${err}`;
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
    } catch (err) {
      status = `Couldn’t save that change: ${err}`;
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
    } catch (err) {
      status = `Couldn’t save that change: ${err}`;
    }
  };

  const toggleMenu = (activityId: number) => {
    openMenuId = openMenuId === activityId ? null : activityId;
  };

  onMount(loadInitial);
</script>

<section class="hero">
  <h2>Acupuncture & Symptom Report</h2>
  <p>Track headache patterns, frequency, and potential triggers over time.</p>
</section>

<section class="card filters">
  <h3>Select Timeframe</h3>
  <div class="grid two">
    <label>
      <div class="label">Start Date</div>
      <input type="date" bind:value={startDate} on:change={loadSummary} />
    </label>
    <label>
      <div class="label">End Date</div>
      <input type="date" bind:value={endDate} on:change={loadSummary} />
    </label>
  </div>

  {#if sessions.length > 0}
    <div style="margin-top: 1rem;">
      <div class="label">Quick Select Session</div>
      <select on:change={(e) => {
        const target = e.target as HTMLSelectElement;
        if (target && target.value) {
          const d = new Date(target.value);
          d.setDate(d.getDate() + 1);
          startDate = d.toISOString().slice(0, 10);
          endDate = new Date().toISOString().slice(0, 10);
          loadSummary();
        }
      }}>
        <option value="">Select a previous Acupuncture session...</option>
        {#each sessions as session}
          <option value={session}>Since {session}</option>
        {/each}
      </select>
    </div>
  {/if}

  {#if status}
    <p class="status-msg" role="alert">{status}</p>
  {/if}
</section>

{#if loading}
  <p style="text-align: center; color: var(--color-neutral-text-muted);">Loading report...</p>
{:else if error}
  <p style="text-align: center; color: var(--color-worse);">{error}</p>
{:else if summary}
  <section class="card stats">
    <div class="stat-box">
      <div class="stat-value">{summary.symptom_days}</div>
      <div class="stat-label">Symptom Days</div>
    </div>
    <div class="stat-box">
      <div class="stat-value">{summary.total_days}</div>
      <div class="stat-label">Total Days in Period</div>
    </div>
    <div class="stat-box">
      <div class="stat-value">{summary.frequency}%</div>
      <div class="stat-label">Frequency</div>
    </div>
    {#if summary.average_severity}
      <div class="stat-box">
        <div class="stat-value">{summary.average_severity}</div>
        <div class="stat-label">Avg Severity</div>
      </div>
    {/if}
  </section>

  <!-- Main list: Possible triggers (the day and night before) -->
  <section class="card results">
    <h3>Possible triggers (the day and night before)</h3>
    <p class="section-desc">
      Factors from the day and evening before a symptom day, compared against symptom-free days.
    </p>

    {#if summary.triggers_day_before.length === 0}
      <p class="empty">
        No clear triggers stood out yet. Items appear here once they have at least {summary.min_nights} days with
        and without them, and show a clear difference.
      </p>
    {:else}
      <ul class="impact-list">
        {#each summary.triggers_day_before as item}
          <li class="impact-row">
            <div class="row-main">
              <div class="row-text">
                <div class="activity-name">{item.activity}</div>
                <div class="activity-detail">
                  <span class="effect" class:better={item.better} class:worse={!item.better}>
                    {fmtRiskEffect(item.effect)}
                  </span>
                  <span class="nights">· {daysLabel(item.with_nights)} with, {item.without_nights} without</span>
                </div>
                {#if item.logged_with && item.logged_with.length}
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
                  <span class="watch-badge" title="Recorded automatically by your Garmin watch">
                    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="7" /><polyline points="12 9 12 12 14 14" /><path d="M12 2v3M12 19v3" />
                    </svg>
                  </span>
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
  </section>

  <!-- Biometrics Analysis -->
  {#if summary.biometrics && summary.biometrics.length > 0}
    <section class="card results">
      <h3>Contributing biometrics (Garmin)</h3>
      <p class="section-desc">
        Garmin physical metrics that showed a noticeable difference before headache days vs clean days.
      </p>

      <ul class="impact-list">
        {#each summary.biometrics as bio}
          <li class="impact-row">
            <div class="row-main">
              <div class="row-text">
                <div class="activity-name">{bio.metric}</div>
                <div class="activity-detail">
                  <span class="effect" class:better={bio.better} class:worse={!bio.better}>
                    {fmtBioDiff(bio.effect, bio.unit)}
                  </span>
                  <span class="nights">· {bio.symptom_avg}{bio.unit ? ` ${bio.unit}` : ''} on symptom days vs {bio.clean_avg}{bio.unit ? ` ${bio.unit}` : ''} clean</span>
                </div>
              </div>

              <div class="row-end">
                <span class="confidence" aria-label={`Confidence: ${confidenceWords[bio.confidence]}`}>
                  <span class="meter" aria-hidden="true">
                    {#each [1, 2, 3] as bar}
                      <i class:on={bar <= confidenceBars[bio.confidence]}></i>
                    {/each}
                  </span>
                  <span class="confidence-word">{confidenceWords[bio.confidence]}</span>
                </span>
                <span class="watch-badge" title="Recorded by Garmin watch">
                  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="7" /><polyline points="12 9 12 12 14 14" /><path d="M12 2v3M12 19v3" />
                  </svg>
                </span>
              </div>
            </div>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <!-- Same Day Section -->
  {#if summary.triggers_same_day && summary.triggers_same_day.length > 0}
    <section class="card results">
      <h3>Same day: could be a cause or a reaction</h3>
      <p class="section-desc">
        Logged on the symptom day itself — kept strictly separate so reactions (e.g. taking a painkiller) aren’t mistaken for triggers.
      </p>

      <ul class="impact-list">
        {#each summary.triggers_same_day as item}
          <li class="impact-row">
            <div class="row-main">
              <div class="row-text">
                <div class="activity-name">{item.activity}</div>
                <div class="activity-detail">
                  <span class="effect" class:better={item.better} class:worse={!item.better}>
                    {fmtFrequencyEffect(item.effect)}
                  </span>
                  <span class="nights">· {daysLabel(item.with_nights)} with, {item.without_nights} without</span>
                </div>
                {#if item.logged_with && item.logged_with.length}
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
    </section>
  {/if}

  <!-- Too early to tell -->
  {#if summary.too_early && summary.too_early.length > 0}
    <section class="card results">
      <h4>Too early to tell</h4>
      <ul class="early-list">
        {#each summary.too_early as item}
          <li>
            <span class="early-name">{item.activity}</span>
            <span class="early-count">{daysLabel(item.with_nights)} so far, needs at least {summary.min_nights}</span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <!-- Left out of this page chips -->
  {#if summary.left_out && summary.left_out.length > 0}
    <section class="card results">
      <h4>Left out of this page</h4>
      <ul class="chip-list">
        {#each summary.left_out as item (item.activity_id)}
          <li class="chip">
            <span>{item.activity} · {reasonWords[item.reason] ?? item.reason}</span>
            <button
              class="chip-remove"
              aria-label={`Bring ${item.activity} back`}
              disabled={savingId !== null}
              on:click={() => bringBack(item)}
            >
              <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
                <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              </svg>
            </button>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  <p class="footnote">
    Triggers are ordered by confidence level, then by effect size. Confidence accounts for sample size and shuffle permutations.
    Garmin hydration treats unlogged days as unknown rather than zero.
  </p>
{/if}

<style>
  .filters {
    padding: 14px 16px;
  }
  .stats {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    padding: 14px 16px;
  }
  .stat-box {
    flex: 1;
    min-width: 100px;
    background: #fff;
    border: 1px solid var(--color-neutral-border);
    padding: 1rem;
    border-radius: 12px;
    text-align: center;
  }
  .stat-value {
    font-size: 1.9rem;
    font-weight: 700;
    color: var(--color-primary-content);
    font-variant-numeric: tabular-nums;
  }
  .stat-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--color-neutral-text-muted);
    text-transform: uppercase;
    margin-top: 0.5rem;
  }

  .results {
    padding: 14px 16px;
    margin-top: 1rem;
  }
  .results h3 {
    margin: 0 0 0.2rem;
    color: var(--color-primary-content);
    font-size: 1.05rem;
  }
  .results h4 {
    margin: 0.5rem 0 0.4rem;
    color: var(--color-neutral-text-muted);
    font-size: 0.86rem;
    font-weight: 600;
  }
  .section-desc {
    font-size: 0.86rem;
    color: var(--color-neutral-text-muted);
    margin: 0 0 0.8rem;
  }

  .status-msg {
    margin: 0.7rem 0 0;
    font-size: 0.9rem;
    background: #fce8e8;
    color: #8a1c1c;
    border-radius: 10px;
    padding: 0.4rem 0.65rem;
  }

  .impact-list,
  .early-list,
  .chip-list {
    list-style: none;
    margin: 0;
    padding: 0;
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

  .menu-button,
  .watch-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 10px;
    background: #edf4fd;
    border: 1px solid #cadcef;
    color: #1e4b76;
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
    padding: 0.25rem 0.65rem;
    font-size: 0.82rem;
    color: var(--color-primary-content);
  }
  .chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: transparent;
    padding: 0;
    cursor: pointer;
    color: var(--color-primary-content);
  }
  .chip-remove:hover {
    color: var(--color-worse);
  }

  .empty {
    color: var(--color-neutral-text-muted);
    font-size: 0.9rem;
    padding: 0.5rem 0;
  }
  .footnote {
    margin: 1.5rem 0 0;
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
    line-height: 1.45;
  }
</style>
