/**
 * Pure calendar-date, session-default, delta, and verdict helpers for the Acupuncture Report.
 * Uses UTC calendar arithmetic on YYYY-MM-DD strings so browser timezones and DST shifts never
 * move a date by a day.
 */

export function addDaysIso(isoDate, days) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  const year = dt.getUTCFullYear();
  const month = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const day = String(dt.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function pastSessionsBefore(sessions, todayIso) {
  if (!Array.isArray(sessions)) return [];
  return sessions.filter((s) => typeof s === 'string' && s < todayIso);
}

export function pickDefaultSessionWindow(sessions, todayIso) {
  const past = pastSessionsBefore(sessions, todayIso);
  if (past.length > 0) {
    return {
      startDate: addDaysIso(past[0], 1),
      endDate: todayIso,
      selectedSession: past[0],
    };
  }
  return {
    startDate: addDaysIso(todayIso, -29),
    endDate: todayIso,
    selectedSession: '',
  };
}

export function barWidthPercent(value, maxValue) {
  if (!Number.isFinite(value) || !Number.isFinite(maxValue) || value <= 0 || maxValue <= 0) {
    return 0;
  }
  const pct = Math.round((value / maxValue) * 100);
  return Math.max(6, Math.min(100, pct));
}

export function formatDeltaPill(currentFreq, previous) {
  if (!previous || typeof previous.frequency !== 'number') return null;
  const prev = previous.frequency;
  if (currentFreq < prev) {
    return { text: `↓ from ${prev}%`, tone: 'better' };
  }
  if (currentFreq > prev) {
    return { text: `↑ from ${prev}%`, tone: 'worse' };
  }
  return { text: `Same as prior (${prev}%)`, tone: 'neutral' };
}

const windowLabel = (window) => {
  if (window === '90d') return 'over the last 90 days';
  if (window === 'all') return 'across all logged history';
  return 'in this period';
};

export function describeVerdict(data) {
  const { verdict_kind, clue_count, logged_days, symptom_days, window, min_nights } = data;
  const scope = windowLabel(window);
  const daysNote = `${logged_days} logged ${logged_days === 1 ? 'day' : 'days'} (${symptom_days} headache ${symptom_days === 1 ? 'day' : 'days'})`;

  if (verdict_kind === 'clues_found') {
    const noun = clue_count === 1 ? 'clue' : 'clues';
    return {
      headline: `${clue_count} ${noun} stood out ${scope}`,
      detail: `Checked across ${daysNote}. Other tested factors looked random.`,
    };
  }

  if (verdict_kind === 'looks_random') {
    return {
      headline: `No clear triggers stood out ${scope}`,
      detail: `Checked across ${daysNote} — so far, your headaches look mostly random rather than tied to one habit or metric.`,
    };
  }

  const suggestion =
    window === 'period'
      ? 'Try switching to 90 days or All time for a fuller picture.'
      : `Each factor needs at least ${min_nights} headache days and ${min_nights} clear logged days to test reliably.`;

  return {
    headline: `Not enough data ${scope} to judge triggers yet`,
    detail: `${daysNote}. ${suggestion}`,
  };
}
