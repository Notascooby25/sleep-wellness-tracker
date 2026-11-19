// Run with: node --test src/lib/acupunctureReport.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  addDaysIso,
  barWidthPercent,
  describeVerdict,
  formatDeltaPill,
  pastSessionsBefore,
  pickDefaultSessionWindow,
} from './acupunctureReport.js';

test('addDaysIso handles month boundaries, leap years, and UK DST transitions safely', () => {
  assert.equal(addDaysIso('2026-03-28', 1), '2026-03-29');
  assert.equal(addDaysIso('2026-10-25', 1), '2026-10-26');
  assert.equal(addDaysIso('2024-02-28', 1), '2024-02-29');
  assert.equal(addDaysIso('2026-01-01', -1), '2025-12-31');
  assert.equal(addDaysIso('2026-11-19', -29), '2026-10-21');
});

test('pastSessionsBefore excludes today and future dates', () => {
  assert.deepEqual(
    pastSessionsBefore(['2026-11-20', '2026-11-19', '2026-11-05', '2026-10-12'], '2026-11-19'),
    ['2026-11-05', '2026-10-12']
  );
});

test('pickDefaultSessionWindow skips today when session already logged today', () => {
  const res = pickDefaultSessionWindow(['2026-11-19', '2026-10-28', '2026-10-01'], '2026-11-19');
  assert.deepEqual(res, {
    startDate: '2026-10-29',
    endDate: '2026-11-19',
    selectedSession: '2026-10-28',
  });
});

test('pickDefaultSessionWindow falls back to 30-day window when only today or no sessions exist', () => {
  assert.deepEqual(pickDefaultSessionWindow(['2026-11-19'], '2026-11-19'), {
    startDate: '2026-10-21',
    endDate: '2026-11-19',
    selectedSession: '',
  });
  assert.deepEqual(pickDefaultSessionWindow([], '2026-11-19'), {
    startDate: '2026-10-21',
    endDate: '2026-11-19',
    selectedSession: '',
  });
});

test('barWidthPercent clamps cleanly with minimum visible floor for positive values', () => {
  assert.equal(barWidthPercent(0, 10), 0);
  assert.equal(barWidthPercent(5, 0), 0);
  assert.equal(barWidthPercent(10, 10), 100);
  assert.equal(barWidthPercent(1, 100), 6);
  assert.equal(barWidthPercent(5, 10), 50);
});

test('formatDeltaPill describes lower, higher, equal, and missing prior periods', () => {
  assert.equal(formatDeltaPill(41, null), null);
  assert.deepEqual(formatDeltaPill(41, { frequency: 52, comparison_type: 'previous_session_gap' }), {
    text: '↓ from 52%',
    tone: 'better',
  });
  assert.deepEqual(formatDeltaPill(60, { frequency: 45, comparison_type: 'equal_length_prior' }), {
    text: '↑ from 45%',
    tone: 'worse',
  });
  assert.deepEqual(formatDeltaPill(40, { frequency: 40, comparison_type: 'previous_session_gap' }), {
    text: 'Same as prior (40%)',
    tone: 'neutral',
  });
});

test('describeVerdict returns plain-English headlines for clues_found, looks_random, and insufficient_data', () => {
  const one = describeVerdict({
    verdict_kind: 'clues_found',
    clue_count: 1,
    logged_days: 60,
    symptom_days: 20,
    window: '90d',
    min_nights: 5,
  });
  assert.match(one.headline, /1 clue stood out/i);
  assert.match(one.detail, /60 logged days/i);

  const two = describeVerdict({
    verdict_kind: 'clues_found',
    clue_count: 2,
    logged_days: 84,
    symptom_days: 31,
    window: '90d',
    min_nights: 5,
  });
  assert.match(two.headline, /2 clues stood out/i);

  const random = describeVerdict({
    verdict_kind: 'looks_random',
    clue_count: 0,
    logged_days: 84,
    symptom_days: 31,
    window: '90d',
    min_nights: 5,
  });
  assert.match(random.headline, /no clear triggers stood out/i);
  assert.match(random.detail, /random/i);

  const shortPeriod = describeVerdict({
    verdict_kind: 'insufficient_data',
    clue_count: 0,
    logged_days: 10,
    symptom_days: 3,
    window: 'period',
    min_nights: 5,
  });
  assert.match(shortPeriod.headline, /not enough data/i);
  assert.match(shortPeriod.detail, /90 days|all time/i);
});
