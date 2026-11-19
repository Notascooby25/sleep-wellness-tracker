export function addDaysIso(isoDate: string, days: number): string;
export function pastSessionsBefore(sessions: string[], todayIso: string): string[];
export function pickDefaultSessionWindow(
  sessions: string[],
  todayIso: string
): { startDate: string; endDate: string; selectedSession: string };
export function barWidthPercent(value: number, maxValue: number): number;
export function formatDeltaPill(
  currentFreq: number,
  previous: { frequency: number; comparison_type: string } | null
): { text: string; tone: 'better' | 'worse' | 'neutral' } | null;
export function describeVerdict(data: {
  verdict_kind: 'clues_found' | 'looks_random' | 'insufficient_data';
  clue_count: number;
  logged_days: number;
  symptom_days: number;
  window: 'period' | '90d' | 'all';
  min_nights: number;
}): { headline: string; detail: string };
