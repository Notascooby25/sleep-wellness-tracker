<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, putJson } from '$lib/api';
  import { describeError } from '$lib/errors.js';
  import {
    addDaysIso,
    barWidthPercent,
    describeVerdict,
    formatDeltaPill,
    pastSessionsBefore,
    pickDefaultSessionWindow
  } from '$lib/acupunctureReport.js';

  type Confidence = 'strong' | 'some' | 'weak';
  type TriggerWindow = 'period' | '90d' | 'all';

  type SymptomBreakdownItem = {
    activity_id: number;
    activity: string;
    days: number;
    is_migraine: boolean;
  };

  type PositionBreakdownItem = {
    position: string;
    days: number;
  };

  type TimelineDay = {
    date: string;
    status: 'clear' | 'headache' | 'migraine';
    symptoms: string[];
    positions: string[];
    has_acupuncture: boolean;
  };

  type PriorPeriod = {
    start_date: string;
    end_date: string;
    total_days: number;
    symptom_days: number;
    frequency: number;
    comparison_type: 'previous_session_gap' | 'equal_length_prior';
  };

  type AppointmentSummaryResponse = {
    start_date: string;
    end_date: string;
    total_days: number;
    symptom_days: number;
    clean_days: number;
    frequency: number;
    average_severity: number | null;
    previous_period: PriorPeriod | null;
    symptom_breakdown: SymptomBreakdownItem[];
    position_breakdown: PositionBreakdownItem[];
    daily_timeline: TimelineDay[];
  };

  type TriggerItem = {
    activity_id: number | null;
    activity: string;
    effect: number;
    with_nights: number;
    without_nights: number;
    confidence: Confidence;
    better: boolean;
    source?: 'activity' | 'garmin';
    kind?: 'activity' | 'garmin_workout';
    timing?: 'day_before' | 'same_day';
    logged_with: string[];
  };

  type BiometricItem = {
    kind?: 'biometric';
    timing?: 'biometric';
    source?: 'garmin';
    metric: string;
    symptom_avg: number;
    clean_avg: number;
    effect: number;
    unit: string;
    with_nights?: number;
    without_nights?: number;
    confidence: Confidence;
    better: boolean;
  };

  type NoClearLinkItem = TriggerItem | BiometricItem;
  type TooEarlyItem = { activity_id: number | null; activity: string; with_nights: number; source?: string };
  type LeftOutItem = { activity_id: number; activity: string; reason: string };

  type TriggersResponse = {
    window: TriggerWindow;
    start_date: string | null;
    end_date: string | null;
    logged_days: number;
    symptom_days: number;
    clean_days: number;
    tested_count: number;
    clue_count: number;
    verdict_kind: 'clues_found' | 'looks_random' | 'insufficient_data';
    triggers_day_before: TriggerItem[];
    triggers_same_day: TriggerItem[];
    biometrics: BiometricItem[];
    no_clear_link: NoClearLinkItem[];
    too_early: TooEarlyItem[];
    left_out: LeftOutItem[];
    min_nights: number;
  };

  type ActivityRecord = { id: number; hidden_pages: string[] | null };

  const PAGE_KEY = 'acupuncture_report';

  const windowOptions: { value: TriggerWindow; label: string }[] = [
    { value: 'period', label: 'This period' },
    { value: '90d', label: '90 days' },
    { value: 'all', label: 'All time' }
  ];

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

  const getUkTodayIso = (): string => {
    try {
      return new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Europe/London',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }).format(new Date());
    } catch {
      return new Date().toISOString().slice(0, 10);
    }
  };

  let todayIso = getUkTodayIso();
  let sessions: string[] = [];
  let selectedSession = '';
  let startDate = '';
  let endDate = '';
  let rangeError = '';

  let summary: AppointmentSummaryResponse | null = null;
  let summaryLoading = true;
  let summaryError = '';
  let inspectedDay: TimelineDay | null = null;

  let triggerWindow: TriggerWindow = '90d';
  let triggers: TriggersResponse | null = null;
  let triggersLoading = true;
  let triggersError = '';

  let status = '';
  let openMenuKey: string | null = null;
  let savingId: number | null = null;

  let summaryReqSeq = 0;
  let triggersReqSeq = 0;

  $: pastSessions = pastSessionsBefore(sessions, todayIso);
  $: deltaPill = summary ? formatDeltaPill(summary.frequency, summary.previous_period) : null;
  $: maxSymptomDays = summary?.symptom_breakdown.length
    ? Math.max(...summary.symptom_breakdown.map((i) => i.days))
    : 0;
  $: maxPositionDays = summary?.position_breakdown.length
    ? Math.max(...summary.position_breakdown.map((i) => i.days))
    : 0;
  $: hasAcupunctureInRange = Boolean(summary?.daily_timeline.some((d) => d.has_acupuncture));
  $: isCompactTimeline = Boolean(summary && summary.daily_timeline.length > 60);
  $: verdict = triggers ? describeVerdict(triggers) : null;
  $: hasClues = Boolean(
    triggers &&
      (triggers.triggers_day_before.length > 0 ||
        triggers.biometrics.length > 0 ||
        triggers.triggers_same_day.length > 0)
  );

  const isBiometricItem = (item: NoClearLinkItem): item is BiometricItem => 'metric' in item;

  const fmtRiskEffect = (effect: number) => {
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    return `${sign}${Math.abs(effect)}% headache risk`;
  };

  const fmtBioDiff = (effect: number, unit: string) => {
    const sign = effect > 0 ? '+' : effect < 0 ? '−' : '';
    const val = Math.abs(effect).toLocaleString('en-GB', { maximumFractionDigits: 1 });
    return unit ? `${sign}${val} ${unit}` : `${sign}${val}`;
  };

  const daysLabel = (n: number) => `${n} ${n === 1 ? 'day' : 'days'}`;

  const fmtShortDate = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d));
    return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
  };

  const fmtDayHeading = (iso: string) => {
    const [y, m, d] = iso.split('-').map(Number);
    const dt = new Date(Date.UTC(y, m - 1, d));
    return dt.toLocaleDateString('en-GB', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      timeZone: 'UTC'
    });
  };

  const dayNumber = (iso: string) => String(Number(iso.slice(8, 10)));

  const dayTooltip = (day: TimelineDay) => {
    const label = fmtDayHeading(day.date);
    const parts: string[] = [label];
    if (day.symptoms.length > 0) {
      parts.push(day.symptoms.join(', '));
    } else {
      parts.push('Clear day');
    }
    if (day.positions.length > 0) {
      parts.push(`Position: ${day.positions.join(', ')}`);
    }
    if (day.has_acupuncture) {
      parts.push('Acupuncture session');
    }
    return parts.join(' · ');
  };

  const priorPeriodTitle = (prior: PriorPeriod | null) => {
    if (!prior) return '';
    const prefix = prior.comparison_type === 'previous_session_gap' ? 'Previous session gap' : `Prior ${daysLabel(prior.total_days)}`;
    return `${prefix}: ${fmtShortDate(prior.start_date)} – ${fmtShortDate(prior.end_date)} (${prior.symptom_days}/${prior.total_days} days)`;
  };

  const bioBarWidth = (bio: BiometricItem) => {
    const base = Math.max(Math.abs(bio.clean_avg), Math.abs(bio.symptom_avg), 1);
    return barWidthPercent(Math.abs(bio.effect), base * 0.5);
  };

  const validateDates = (): boolean => {
    if (!startDate || !endDate) {
      rangeError = 'Please choose both a start date and an end date.';
      return false;
    }
    if (startDate > endDate) {
      rangeError = 'Start date must be on or before end date.';
      return false;
    }
    rangeError = '';
    return true;
  };

  const loadSummary = async () => {
    if (!validateDates()) {
      summaryLoading = false;
      return;
    }
    const seq = ++summaryReqSeq;
    summaryLoading = true;
    summaryError = '';
    inspectedDay = null;
    try {
      const data = await getJson<AppointmentSummaryResponse>(
        `/reports/headache-appointment-summary?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`
      );
      if (seq !== summaryReqSeq) return;
      summary = data;
    } catch (err) {
      if (seq !== summaryReqSeq) return;
      summaryError = `Couldn’t load the appointment summary: ${describeError(err)}`;
      summary = null;
    } finally {
      if (seq === summaryReqSeq) summaryLoading = false;
    }
  };

  const loadTriggers = async () => {
    if (triggerWindow === 'period' && !validateDates()) {
      triggersLoading = false;
      return;
    }
    const seq = ++triggersReqSeq;
    triggersLoading = true;
    triggersError = '';
    openMenuKey = null;
    try {
      const params = new URLSearchParams({ window: triggerWindow });
      if (triggerWindow === 'period') {
        params.set('start_date', startDate);
        params.set('end_date', endDate);
      }
      const data = await getJson<TriggersResponse>(`/reports/headache-triggers?${params.toString()}`);
      if (seq !== triggersReqSeq) return;
      triggers = data;
    } catch (err) {
      if (seq !== triggersReqSeq) return;
      triggersError = `Couldn’t load trigger clues: ${describeError(err)}`;
      triggers = null;
    } finally {
      if (seq === triggersReqSeq) triggersLoading = false;
    }
  };

  const handleDateChange = () => {
    selectedSession = '';
    void loadSummary();
    if (triggerWindow === 'period') {
      void loadTriggers();
    }
  };

  const handleSessionSelect = () => {
    if (!selectedSession) return;
    startDate = addDaysIso(selectedSession, 1);
    endDate = todayIso;
    void loadSummary();
    if (triggerWindow === 'period') {
      void loadTriggers();
    }
  };

  const selectTriggerWindow = (next: TriggerWindow) => {
    if (triggerWindow === next) return;
    triggerWindow = next;
    void loadTriggers();
  };

  const toggleDayInspect = (day: TimelineDay) => {
    inspectedDay = inspectedDay?.date === day.date ? null : day;
  };

  const saveSettings = async (activityId: number, body: Record<string, unknown>) => {
    savingId = activityId;
    status = '';
    try {
      await putJson(`/activities/${activityId}/report-settings`, body);
      await loadTriggers();
    } catch (err) {
      status = `Couldn’t save that change: ${describeError(err)}`;
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
      status = `Couldn’t save that change: ${describeError(err)}`;
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
      status = `Couldn’t save that change: ${describeError(err)}`;
    }
  };

  const toggleMenu = (key: string) => {
    openMenuKey = openMenuKey === key ? null : key;
  };

  const loadInitial = async () => {
    todayIso = getUkTodayIso();
    // Kick off default 90-day triggers in parallel immediately — it does not depend on session dates
    const triggersPromise = loadTriggers();
    try {
      const sessRes = await getJson<{ sessions: string[] }>('/reports/acupuncture-sessions');
      sessions = sessRes?.sessions || [];
    } catch {
      sessions = [];
    }
    const defaults = pickDefaultSessionWindow(sessions, todayIso);
    startDate = defaults.startDate;
    endDate = defaults.endDate;
    selectedSession = defaults.selectedSession;

    await Promise.all([loadSummary(), triggersPromise]);
  };

  onMount(loadInitial);
</script>

<svelte:head>
  <title>Acupuncture &amp; Symptom Report · Sleep Wellness Tracker</title>
</svelte:head>

<section class="hero">
  <h1>Acupuncture &amp; Symptom Report</h1>
  <p>A quick-glance clinic brief since your last appointment, plus longer-term trigger clues.</p>
</section>

<!-- Compact Timeframe Bar -->
<section class="card filters" aria-label="Report timeframe">
  <div class="filters-grid">
    {#if pastSessions.length > 0}
      <label class="session-field">
        <span class="label">Quick Select Session</span>
        <select bind:value={selectedSession} on:change={handleSessionSelect}>
          <option value="">Custom date range…</option>
          {#each pastSessions as session}
            <option value={session}>Since {fmtShortDate(session)} ({session})</option>
          {/each}
        </select>
      </label>
    {/if}

    <label>
      <span class="label">Start Date</span>
      <input type="date" bind:value={startDate} on:change={handleDateChange} />
    </label>

    <label>
      <span class="label">End Date</span>
      <input type="date" bind:value={endDate} on:change={handleDateChange} />
    </label>
  </div>

  {#if rangeError}
    <p class="status-msg" role="alert">{rangeError}</p>
  {/if}
  {#if status}
    <p class="status-msg" role="alert">{status}</p>
  {/if}
</section>

<!-- Appointment Summary (Clinic Brief) -->
<section class="card brief" aria-label="Appointment summary">
  <div class="section-head">
    <div>
      <h3>Since Last Appointment</h3>
      {#if summary}
        <p class="section-desc">
          {fmtShortDate(summary.start_date)} – {fmtShortDate(summary.end_date)} · {daysLabel(summary.total_days)}
        </p>
      {/if}
    </div>
  </div>

  {#if summaryLoading && !summary}
    <div class="skeleton-block" aria-busy="true">
      <div class="skeleton-line wide"></div>
      <div class="skeleton-line"></div>
    </div>
  {:else if summaryError}
    <p class="error-text" role="alert">{summaryError}</p>
  {:else if summary}
    <div class="stat-strip" class:loading-fade={summaryLoading}>
      <div class="stat-cell">
        <div class="stat-value">{summary.symptom_days}</div>
        <div class="stat-label">Symptom Days</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{summary.total_days}</div>
        <div class="stat-label">Total Days</div>
      </div>
      <div class="stat-cell">
        <div class="stat-value">{summary.frequency}%</div>
        <div class="stat-label">Frequency</div>
        {#if deltaPill}
          <span
            class="delta-pill"
            class:better={deltaPill.tone === 'better'}
            class:worse={deltaPill.tone === 'worse'}
            title={priorPeriodTitle(summary.previous_period)}
          >
            {deltaPill.text}
          </span>
        {/if}
      </div>
      {#if summary.average_severity !== null}
        <div class="stat-cell">
          <div class="stat-value">{summary.average_severity}</div>
          <div class="stat-label">Avg Severity</div>
        </div>
      {/if}
    </div>

    <!-- Day-by-Day Timeline Strip -->
    <div class="sub-section">
      <div class="sub-head">
        <h4>When symptoms happened</h4>
        <span class="sub-hint">Tap any day for details</span>
      </div>

      <div
        class="timeline-grid"
        class:compact={isCompactTimeline}
        role="list"
        aria-label="Day-by-day symptom timeline"
      >
        {#each summary.daily_timeline as day (day.date)}
          <button
            type="button"
            class="day-cell"
            class:headache={day.status === 'headache'}
            class:migraine={day.status === 'migraine'}
            class:selected={inspectedDay?.date === day.date}
            title={dayTooltip(day)}
            aria-label={dayTooltip(day)}
            aria-pressed={inspectedDay?.date === day.date}
            on:click={() => toggleDayInspect(day)}
          >
            {#if !isCompactTimeline}
              <span>{dayNumber(day.date)}</span>
            {/if}
            {#if day.has_acupuncture}
              <i class="acu-dot" aria-hidden="true"></i>
            {/if}
          </button>
        {/each}
      </div>

      <div class="legend" aria-hidden="true">
        <span><i class="legend-swatch clear"></i> Clear</span>
        <span><i class="legend-swatch headache"></i> Headache</span>
        <span><i class="legend-swatch migraine"></i> Migraine</span>
        {#if hasAcupunctureInRange}
          <span><i class="legend-swatch acu"></i> Acupuncture</span>
        {/if}
      </div>

      {#if inspectedDay}
        <div class="day-detail" role="region" aria-label="Selected day details">
          <div class="day-detail-text">
            <strong>{fmtDayHeading(inspectedDay.date)}</strong>
            {#if inspectedDay.symptoms.length > 0}
              <span> · {inspectedDay.symptoms.join(', ')}</span>
            {:else}
              <span> · Clear day</span>
            {/if}
            {#if inspectedDay.positions.length > 0}
              <span class="detail-muted"> · Position: {inspectedDay.positions.join(', ')}</span>
            {/if}
            {#if inspectedDay.has_acupuncture}
              <span class="acu-tag">Acupuncture</span>
            {/if}
          </div>
          <button
            type="button"
            class="detail-close"
            aria-label="Close day details"
            on:click={() => (inspectedDay = null)}
          >
            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </div>
      {/if}
    </div>

    <!-- Breakdown Columns -->
    <div class="sub-section breakdowns" class:single={summary.position_breakdown.length === 0}>
      <div>
        <h4>Headache Types</h4>
        {#if summary.symptom_breakdown.length === 0}
          <p class="empty">No headaches logged in this period.</p>
        {:else}
          <ul class="bar-list">
            {#each summary.symptom_breakdown as item (item.activity_id)}
              <li class="bar-item">
                <div class="bar-row-top">
                  <span class="bar-name">{item.activity}</span>
                  <strong class="bar-count">{daysLabel(item.days)}</strong>
                </div>
                <div class="bar-track" aria-hidden="true">
                  <div
                    class="bar-fill"
                    class:migraine={item.is_migraine}
                    class:headache={!item.is_migraine}
                    style={`width: ${barWidthPercent(item.days, maxSymptomDays)}%`}
                  ></div>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      {#if summary.position_breakdown.length > 0}
        <div>
          <h4>Positions Logged</h4>
          <ul class="bar-list">
            {#each summary.position_breakdown as pos (pos.position)}
              <li class="bar-item">
                <div class="bar-row-top">
                  <span class="bar-name">{pos.position}</span>
                  <strong class="bar-count">{daysLabel(pos.days)}</strong>
                </div>
                <div class="bar-track" aria-hidden="true">
                  <div
                    class="bar-fill position"
                    style={`width: ${barWidthPercent(pos.days, maxPositionDays)}%`}
                  ></div>
                </div>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    </div>
  {/if}
</section>

<!-- Possible Triggers Card -->
<section class="card results" aria-label="Possible headache triggers">
  <div class="triggers-header">
    <div>
      <h3>Possible Triggers</h3>
      <p class="section-desc">Comparing days you logged each factor against your other logged days.</p>
    </div>

    <div class="window-toggle" role="group" aria-label="Trigger analysis timeframe">
      {#each windowOptions as opt}
        <button
          type="button"
          class="seg-btn"
          class:active={triggerWindow === opt.value}
          aria-pressed={triggerWindow === opt.value}
          on:click={() => selectTriggerWindow(opt.value)}
        >
          {opt.label}
        </button>
      {/each}
    </div>
  </div>

  {#if triggersLoading && !triggers}
    <div class="skeleton-block" aria-busy="true">
      <div class="skeleton-line wide"></div>
      <div class="skeleton-line"></div>
    </div>
  {:else if triggersError}
    <p class="error-text" role="alert">{triggersError}</p>
  {:else if triggers && verdict}
    <!-- Verdict Banner -->
    <div
      class="verdict-banner"
      class:clues={triggers.verdict_kind === 'clues_found'}
      class:loading-fade={triggersLoading}
    >
      <div class="verdict-text">
        <div class="verdict-headline">{verdict.headline}</div>
        <div class="verdict-detail">{verdict.detail}</div>
      </div>
      {#if triggers.verdict_kind === 'insufficient_data' && triggerWindow === 'period'}
        <button type="button" class="btn-switch" on:click={() => selectTriggerWindow('90d')}>
          Switch to 90 days
        </button>
      {/if}
    </div>

    {#if hasClues}
      <!-- Day & night before clues -->
      {#if triggers.triggers_day_before.length > 0}
        <div class="clue-group">
          <h4>Day and night before</h4>
          <p class="group-desc">Factors logged the day or evening before a headache day.</p>
          <ul class="impact-list">
            {#each triggers.triggers_day_before as item (`db:${item.activity_id ?? item.activity}`)}
              {@const menuKey = `db:${item.activity_id}`}
              <li class="impact-row">
                <div class="row-main">
                  <div class="row-text">
                    <div class="activity-name">{item.activity}</div>
                    <div class="activity-detail">
                      <span class="risk-track" aria-hidden="true">
                        <span
                          class="risk-fill"
                          class:better={item.better}
                          class:worse={!item.better}
                          style={`width: ${barWidthPercent(Math.abs(item.effect), 100)}%`}
                        ></span>
                      </span>
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
                        type="button"
                        class="menu-button"
                        aria-label={`Change how ${item.activity} is used`}
                        aria-expanded={openMenuKey === menuKey}
                        disabled={savingId !== null}
                        on:click={() => toggleMenu(menuKey)}
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

                {#if item.activity_id !== null && openMenuKey === menuKey}
                  {@const id = item.activity_id}
                  <div class="role-menu">
                    <p class="role-question">What is “{item.activity}” for you?</p>
                    {#each roleChoices as choice}
                      <button type="button" class="role-choice" disabled={savingId !== null} on:click={() => chooseRole(id, choice.role)}>
                        <span class="choice-label">{choice.label}</span>
                        <span class="choice-hint">{choice.hint}</span>
                      </button>
                    {/each}
                    <button type="button" class="role-cancel" on:click={() => (openMenuKey = null)}>Cancel</button>
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- Biometrics clues -->
      {#if triggers.biometrics.length > 0}
        <div class="clue-group">
          <h4>Contributing biometrics (Garmin)</h4>
          <p class="group-desc">Garmin readings that showed a clear gap before headache days vs clear logged days.</p>
          <ul class="impact-list">
            {#each triggers.biometrics as bio (bio.metric)}
              <li class="impact-row">
                <div class="row-main">
                  <div class="row-text">
                    <div class="activity-name">{bio.metric}</div>
                    <div class="activity-detail">
                      <span class="risk-track" aria-hidden="true">
                        <span
                          class="risk-fill"
                          class:better={bio.better}
                          class:worse={!bio.better}
                          style={`width: ${bioBarWidth(bio)}%`}
                        ></span>
                      </span>
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
                    <span class="watch-badge" title="Recorded automatically by your Garmin watch">
                      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="7" /><polyline points="12 9 12 12 14 14" /><path d="M12 2v3M12 19v3" />
                      </svg>
                    </span>
                  </div>
                </div>
              </li>
            {/each}
          </ul>
        </div>
      {/if}

      <!-- Same-day clues -->
      {#if triggers.triggers_same_day.length > 0}
        <div class="clue-group">
          <h4>Same day: could be a cause or a reaction</h4>
          <p class="group-desc">Logged on the symptom day itself — mark reactions via the menu so they stay out of triggers.</p>
          <ul class="impact-list">
            {#each triggers.triggers_same_day as item (`sd:${item.activity_id ?? item.activity}`)}
              {@const menuKey = `sd:${item.activity_id}`}
              <li class="impact-row">
                <div class="row-main">
                  <div class="row-text">
                    <div class="activity-name">{item.activity}</div>
                    <div class="activity-detail">
                      <span class="risk-track" aria-hidden="true">
                        <span
                          class="risk-fill"
                          class:better={item.better}
                          class:worse={!item.better}
                          style={`width: ${barWidthPercent(Math.abs(item.effect), 100)}%`}
                        ></span>
                      </span>
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
                        type="button"
                        class="menu-button"
                        aria-label={`Change how ${item.activity} is used`}
                        aria-expanded={openMenuKey === menuKey}
                        disabled={savingId !== null}
                        on:click={() => toggleMenu(menuKey)}
                      >
                        <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
                          <circle cx="4.5" cy="10" r="1.6" /><circle cx="10" cy="10" r="1.6" /><circle cx="15.5" cy="10" r="1.6" />
                        </svg>
                      </button>
                    {/if}
                  </div>
                </div>

                {#if item.activity_id !== null && openMenuKey === menuKey}
                  {@const id = item.activity_id}
                  <div class="role-menu">
                    <p class="role-question">What is “{item.activity}” for you?</p>
                    {#each roleChoices as choice}
                      <button type="button" class="role-choice" disabled={savingId !== null} on:click={() => chooseRole(id, choice.role)}>
                        <span class="choice-label">{choice.label}</span>
                        <span class="choice-hint">{choice.hint}</span>
                      </button>
                    {/each}
                    <button type="button" class="role-cancel" on:click={() => (openMenuKey = null)}>Cancel</button>
                  </div>
                {/if}
              </li>
            {/each}
          </ul>
        </div>
      {/if}
    {/if}

    <!-- Collapsible Secondary Drawers -->
    <div class="drawers">
      {#if triggers.no_clear_link.length > 0}
        <details class="drawer">
          <summary>
            <span class="drawer-title">Checked, no clear link ({triggers.no_clear_link.length})</span>
            <svg class="chevron" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M5 3.5L10.5 8 5 12.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </summary>
          <ul class="impact-list drawer-body">
            {#each triggers.no_clear_link as item, idx (`ncl:${isBiometricItem(item) ? item.metric : (item.activity_id ?? item.activity)}:${idx}`)}
              {#if isBiometricItem(item)}
                <li class="impact-row">
                  <div class="row-main">
                    <div class="row-text">
                      <div class="activity-name muted-name">{item.metric}</div>
                      <div class="activity-detail">
                        <span>{fmtBioDiff(item.effect, item.unit)}</span>
                        <span class="nights">· {item.symptom_avg}{item.unit ? ` ${item.unit}` : ''} symptom vs {item.clean_avg}{item.unit ? ` ${item.unit}` : ''} clean</span>
                      </div>
                    </div>
                    <div class="row-end">
                      <span class="confidence-quiet">{confidenceWords[item.confidence]}</span>
                      <span class="watch-badge" title="Recorded automatically by your Garmin watch">
                        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">
                          <circle cx="12" cy="12" r="7" /><polyline points="12 9 12 12 14 14" /><path d="M12 2v3M12 19v3" />
                        </svg>
                      </span>
                    </div>
                  </div>
                </li>
              {:else}
                {@const menuKey = `ncl:${item.activity_id}`}
                <li class="impact-row">
                  <div class="row-main">
                    <div class="row-text">
                      <div class="activity-name muted-name">{item.activity}</div>
                      <div class="activity-detail">
                        <span>{fmtRiskEffect(item.effect)}</span>
                        <span class="nights">· {daysLabel(item.with_nights)} with, {item.without_nights} without</span>
                      </div>
                    </div>
                    <div class="row-end">
                      <span class="confidence-quiet">{confidenceWords[item.confidence]}</span>
                      {#if item.activity_id !== null}
                        {@const id = item.activity_id}
                        <button
                          type="button"
                          class="menu-button"
                          aria-label={`Change how ${item.activity} is used`}
                          aria-expanded={openMenuKey === menuKey}
                          disabled={savingId !== null}
                          on:click={() => toggleMenu(menuKey)}
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
                  {#if item.activity_id !== null && openMenuKey === menuKey}
                    {@const id = item.activity_id}
                    <div class="role-menu">
                      <p class="role-question">What is “{item.activity}” for you?</p>
                      {#each roleChoices as choice}
                        <button type="button" class="role-choice" disabled={savingId !== null} on:click={() => chooseRole(id, choice.role)}>
                          <span class="choice-label">{choice.label}</span>
                          <span class="choice-hint">{choice.hint}</span>
                        </button>
                      {/each}
                      <button type="button" class="role-cancel" on:click={() => (openMenuKey = null)}>Cancel</button>
                    </div>
                  {/if}
                </li>
              {/if}
            {/each}
          </ul>
        </details>
      {/if}

      {#if triggers.too_early.length > 0}
        <details class="drawer">
          <summary>
            <span class="drawer-title">Too early to tell ({triggers.too_early.length})</span>
            <svg class="chevron" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M5 3.5L10.5 8 5 12.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </summary>
          <ul class="early-list drawer-body">
            {#each triggers.too_early as item (`early:${item.activity_id ?? item.activity}`)}
              <li>
                <span class="early-name">{item.activity}</span>
                <span class="early-count">{daysLabel(item.with_nights)} so far, needs at least {triggers.min_nights}</span>
              </li>
            {/each}
          </ul>
        </details>
      {/if}

      {#if triggers.left_out.length > 0}
        <details class="drawer">
          <summary>
            <span class="drawer-title">Left out of this page ({triggers.left_out.length})</span>
            <svg class="chevron" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
              <path d="M5 3.5L10.5 8 5 12.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </summary>
          <ul class="chip-list drawer-body">
            {#each triggers.left_out as item (item.activity_id)}
              <li class="chip">
                <span>{item.activity} · {reasonWords[item.reason] ?? item.reason}</span>
                <button
                  type="button"
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
        </details>
      {/if}
    </div>
  {/if}
</section>

<p class="footnote">
  Clues are checked with shuffle tests and adjusted for testing multiple factors at once, using only days you logged in the app.
  Garmin hydration treats unlogged days as unknown rather than zero.
</p>

<style>
  .filters {
    padding: 14px 16px;
  }
  .filters-grid {
    display: grid;
    grid-template-columns: minmax(210px, 1.4fr) repeat(2, minmax(140px, 1fr));
    gap: 0.75rem;
    align-items: end;
  }
  .filters label {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  .filters select,
  .filters input[type='date'] {
    min-height: 44px;
    border-radius: 10px;
    border: 1px solid var(--color-input-border);
    background: var(--color-neutral-bg);
    color: var(--color-neutral-text);
    padding: 0.45rem 0.6rem;
    font: inherit;
    font-size: 0.92rem;
  }

  .brief,
  .results {
    padding: 16px;
    margin-top: 12px;
  }
  .section-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
  }
  .brief h3,
  .results h3 {
    margin: 0 0 0.15rem;
    color: var(--color-primary-content);
    font-size: 1.08rem;
  }
  .section-desc {
    font-size: 0.86rem;
    color: var(--color-neutral-text-muted);
    margin: 0;
  }
  .loading-fade {
    opacity: 0.6;
    transition: opacity 160ms ease-out;
  }

  /* Stat strip — flat tonal cells inside the Clinic Brief card */
  .stat-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(115px, 1fr));
    gap: 10px;
    margin-bottom: 1rem;
  }
  .stat-cell {
    background: var(--color-surface-subtle);
    border: 1px solid var(--color-neutral-border);
    border-radius: 12px;
    padding: 0.85rem 0.75rem;
    text-align: center;
  }
  .stat-value {
    font-size: 1.8rem;
    font-weight: 700;
    color: var(--color-primary-content);
    font-variant-numeric: tabular-nums;
    line-height: 1.15;
  }
  .stat-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: var(--color-neutral-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-top: 0.3rem;
  }
  .delta-pill {
    display: inline-block;
    margin-top: 0.35rem;
    padding: 0.14rem 0.55rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 600;
    background: var(--color-surface-muted);
    color: var(--color-slate-text);
    font-variant-numeric: tabular-nums;
  }
  .delta-pill.better {
    background: var(--color-success-bg);
    color: var(--color-success-text);
  }
  .delta-pill.worse {
    background: var(--color-error-bg);
    color: var(--color-error);
  }

  /* Sub-sections separated by quiet borders */
  .sub-section {
    padding-top: 1rem;
    margin-top: 1rem;
    border-top: 1px solid var(--color-surface-muted);
  }
  .sub-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.65rem;
  }
  .brief h4,
  .clue-group h4 {
    margin: 0 0 0.45rem;
    color: var(--color-slate-text);
    font-size: 0.82rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .sub-head h4 {
    margin: 0;
  }
  .sub-hint {
    font-size: 0.78rem;
    color: var(--color-neutral-text-faint);
  }

  /* Day-by-day timeline */
  .timeline-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(34px, 1fr));
    gap: 6px;
  }
  .timeline-grid.compact {
    grid-template-columns: repeat(auto-fill, minmax(16px, 1fr));
    gap: 4px;
  }
  .day-cell {
    position: relative;
    height: 34px;
    padding: 0;
    border-radius: 8px;
    border: 1px solid var(--color-neutral-border);
    background: var(--color-surface-subtle);
    color: var(--color-neutral-text-muted);
    font: inherit;
    font-size: 0.78rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: border-color 140ms ease-out, background-color 140ms ease-out;
  }
  .timeline-grid.compact .day-cell {
    height: 16px;
    border-radius: 6px;
  }
  .day-cell.headache {
    background: #fdecc8;
    border-color: #e6b86a;
    color: #7c4d08;
  }
  .day-cell.migraine {
    background: #f9d6d5;
    border-color: #d98a88;
    color: #8a1c1c;
  }
  .day-cell.selected {
    border-color: var(--color-accent-border);
    outline: 2px solid var(--color-accent);
    outline-offset: 1px;
  }
  .acu-dot {
    position: absolute;
    top: 3px;
    right: 3px;
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--color-accent);
  }
  .timeline-grid.compact .acu-dot {
    top: 2px;
    right: 2px;
    width: 4px;
    height: 4px;
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 0.85rem;
    margin-top: 0.65rem;
    font-size: 0.78rem;
    color: var(--color-neutral-text-muted);
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .legend-swatch {
    width: 11px;
    height: 11px;
    border-radius: 4px;
    display: inline-block;
  }
  .legend-swatch.clear {
    background: var(--color-surface-subtle);
    border: 1px solid var(--color-neutral-border);
  }
  .legend-swatch.headache {
    background: #fdecc8;
    border: 1px solid #e6b86a;
  }
  .legend-swatch.migraine {
    background: #f9d6d5;
    border: 1px solid #d98a88;
  }
  .legend-swatch.acu {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: var(--color-accent);
  }

  .day-detail {
    margin-top: 0.75rem;
    padding: 0.6rem 0.8rem;
    border-radius: 10px;
    border: 1px solid var(--color-primary-border-soft);
    background: var(--color-surface-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    font-size: 0.86rem;
    color: var(--color-neutral-text);
  }
  .detail-muted {
    color: var(--color-neutral-text-muted);
  }
  .acu-tag {
    display: inline-block;
    margin-left: 0.4rem;
    padding: 0.1rem 0.5rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--color-primary);
    color: var(--color-primary-content);
    border: 1px solid var(--color-primary-border);
  }
  .detail-close {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    border: 1px solid var(--color-input-border);
    background: var(--color-neutral-bg);
    color: var(--color-link);
    cursor: pointer;
  }

  /* Breakdown bars */
  .breakdowns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 1.25rem;
  }
  .breakdowns.single {
    grid-template-columns: 1fr;
  }
  .bar-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }
  .bar-row-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.5rem;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
  }
  .bar-name {
    color: var(--color-neutral-text);
    font-weight: 500;
  }
  .bar-count {
    color: var(--color-primary-content);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
  }
  .bar-track {
    height: 8px;
    border-radius: 999px;
    background: var(--color-surface-muted);
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    border-radius: 999px;
    background: var(--color-accent);
  }
  .bar-fill.headache {
    background: #c88a2b;
  }
  .bar-fill.migraine {
    background: var(--color-worse);
  }
  .bar-fill.position {
    background: var(--color-confidence);
  }

  /* Triggers header + segmented toggle */
  .triggers-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.85rem;
    flex-wrap: wrap;
    margin-bottom: 0.85rem;
  }
  .window-toggle {
    display: inline-flex;
    padding: 3px;
    gap: 3px;
    border-radius: 10px;
    background: var(--color-surface-subtle);
    border: 1px solid var(--color-neutral-border);
  }
  .seg-btn {
    min-height: 38px;
    padding: 0.35rem 0.7rem;
    border-radius: 8px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--color-neutral-text-muted);
    font: inherit;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 140ms ease-out, color 140ms ease-out;
  }
  .seg-btn.active {
    background: var(--color-primary);
    border-color: var(--color-primary-border);
    color: var(--color-primary-content);
  }

  /* Verdict banner */
  .verdict-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.85rem;
    flex-wrap: wrap;
    padding: 0.8rem 0.95rem;
    border-radius: 12px;
    border: 1px solid var(--color-neutral-border);
    background: var(--color-surface-subtle);
    margin-bottom: 0.9rem;
  }
  .verdict-banner.clues {
    background: var(--color-primary);
    border-color: var(--color-primary-border);
  }
  .verdict-headline {
    font-weight: 700;
    color: var(--color-primary-content);
    font-size: 0.96rem;
  }
  .verdict-detail {
    margin-top: 0.15rem;
    font-size: 0.84rem;
    color: var(--color-slate-text);
  }
  .btn-switch {
    min-height: 40px;
    padding: 0.4rem 0.8rem;
    border-radius: 10px;
    border: 1px solid var(--color-primary-border);
    background: var(--color-primary);
    color: var(--color-primary-content);
    font: inherit;
    font-size: 0.84rem;
    font-weight: 600;
    cursor: pointer;
  }

  .clue-group {
    padding-top: 0.9rem;
    margin-top: 0.9rem;
    border-top: 1px solid var(--color-surface-muted);
  }
  .clue-group:first-of-type {
    padding-top: 0.2rem;
    margin-top: 0;
    border-top: none;
  }
  .group-desc {
    margin: -0.2rem 0 0.6rem;
    font-size: 0.84rem;
    color: var(--color-neutral-text-muted);
  }

  .impact-list,
  .early-list,
  .chip-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .impact-row {
    border-top: 1px solid var(--color-surface-muted);
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
  .activity-name.muted-name {
    font-weight: 600;
    color: var(--color-slate-text);
  }
  .activity-detail {
    margin-top: 0.2rem;
    font-size: 0.85rem;
    color: var(--color-neutral-text-muted);
    font-variant-numeric: tabular-nums;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .risk-track {
    width: 56px;
    height: 6px;
    border-radius: 999px;
    background: var(--color-surface-muted);
    overflow: hidden;
    display: inline-block;
    flex-shrink: 0;
  }
  .risk-fill {
    display: block;
    height: 100%;
    border-radius: 999px;
  }
  .risk-fill.better {
    background: var(--color-better);
  }
  .risk-fill.worse {
    background: var(--color-worse);
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
    margin-top: 0.25rem;
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
    gap: 0.4rem;
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
  }
  .confidence-quiet {
    font-size: 0.78rem;
    color: var(--color-neutral-text-faint);
  }
  .meter {
    display: inline-flex;
    gap: 3px;
  }
  .meter i {
    display: block;
    width: 14px;
    height: 7px;
    border-radius: 999px;
    background: var(--color-confidence-off);
  }
  .meter i.on {
    background: var(--color-confidence);
  }
  .confidence-word {
    min-width: 6.4em;
  }

  .menu-button,
  .watch-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    border-radius: 10px;
    background: var(--color-surface-subtle);
    border: 1px solid var(--color-input-border);
    color: var(--color-link);
    fill: var(--color-link);
    cursor: pointer;
    transition: background-color 160ms ease-out;
  }
  .watch-badge {
    cursor: default;
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
    padding: 0.65rem;
    border: 1px solid var(--color-input-border);
    border-radius: 12px;
    background: var(--color-bg-start);
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
    padding: 0.55rem 0.65rem;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--color-neutral-text);
    cursor: pointer;
    transition: background-color 160ms ease-out;
  }
  .role-choice:hover:not(:disabled) {
    background: var(--color-surface-muted);
    border-color: var(--color-input-border);
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
    min-height: 36px;
    padding: 0.35rem 0.75rem;
    border-radius: 10px;
    border: 1px solid var(--color-input-border);
    background: var(--color-neutral-bg);
    color: var(--color-link);
    font-size: 0.84rem;
    cursor: pointer;
  }

  /* Collapsible secondary drawers */
  .drawers {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  .drawer {
    border-top: 1px solid var(--color-surface-muted);
    padding-top: 0.35rem;
  }
  .drawer summary {
    list-style: none;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    cursor: pointer;
    color: var(--color-slate-text);
    font-size: 0.88rem;
    font-weight: 600;
    border-radius: 10px;
    padding: 0.25rem 0.4rem;
  }
  .drawer summary::-webkit-details-marker {
    display: none;
  }
  .drawer summary:hover {
    background: var(--color-surface-subtle);
  }
  .chevron {
    color: var(--color-neutral-text-muted);
    transition: transform 160ms ease-out;
  }
  .drawer[open] .chevron {
    transform: rotate(90deg);
  }
  .drawer-body {
    padding: 0.25rem 0.4rem 0.5rem;
  }

  .early-list li {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.2rem 0.75rem;
    padding: 0.45rem 0;
    border-top: 1px solid var(--color-surface-subtle);
    font-size: 0.88rem;
  }
  .early-list li:first-child {
    border-top: none;
  }
  .early-name {
    color: var(--color-neutral-text-muted);
    font-weight: 600;
  }
  .early-count {
    color: var(--color-neutral-text-faint);
    font-size: 0.83rem;
    font-variant-numeric: tabular-nums;
  }

  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 999px;
    border: 1px solid var(--color-input-border);
    background: var(--color-surface-subtle);
    padding: 0.25rem 0.65rem;
    font-size: 0.82rem;
    color: var(--color-primary-content);
  }
  .chip-remove {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 999px;
    background: transparent;
    padding: 0;
    cursor: pointer;
    color: var(--color-primary-content);
  }
  .chip-remove:hover {
    color: var(--color-worse);
  }

  .status-msg {
    margin: 0.75rem 0 0;
    font-size: 0.88rem;
    background: var(--color-error-bg);
    color: var(--color-error);
    border-radius: 10px;
    padding: 0.45rem 0.7rem;
  }
  .error-text {
    color: var(--color-error);
    font-size: 0.9rem;
    margin: 0.5rem 0;
  }
  .empty {
    color: var(--color-neutral-text-muted);
    font-size: 0.9rem;
    margin: 0.3rem 0 0;
  }
  .footnote {
    margin: 1.25rem 0 0;
    font-size: 0.8rem;
    color: var(--color-neutral-text-muted);
    line-height: 1.45;
  }

  .skeleton-block {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    padding: 0.4rem 0;
  }
  .skeleton-line {
    height: 14px;
    width: 55%;
    border-radius: 8px;
    background: var(--color-surface-muted);
  }
  .skeleton-line.wide {
    width: 85%;
  }

  @media (max-width: 860px) {
    .filters-grid {
      grid-template-columns: 1fr 1fr;
    }
    .session-field {
      grid-column: 1 / -1;
    }
    .breakdowns {
      grid-template-columns: 1fr;
    }
    .row-main {
      align-items: flex-start;
      flex-direction: column;
    }
    .row-end {
      width: 100%;
      justify-content: space-between;
    }
    .confidence-word {
      min-width: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .loading-fade,
    .day-cell,
    .seg-btn,
    .menu-button,
    .role-choice,
    .chevron {
      transition: none;
    }
  }
</style>
