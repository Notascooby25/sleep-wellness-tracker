with open('frontend-web/src/routes/analytics/+page.svelte', 'r') as f:
    content = f.read()

# Append to Correlations & Insights Computed Properties
new_computed = """
  // -- Subjective vs Objective Sleep --
  $: sleepGapList = entries
    .filter(e => e.subjective_sleep_rating !== null)
    .map(e => {
      const gDate = String(e.timestamp).split('T')[0];
      const objSleepRow = sleepByDateMap.get(gDate);
      if (!objSleepRow || typeof objSleepRow.sleep_score !== 'number') return null;
      // Map 1(Great)->100, 5(Crisis)->0
      const subjScore = ((5 - e.subjective_sleep_rating!) / 4) * 100;
      return {
        date: gDate,
        subj: subjScore,
        obj: objSleepRow.sleep_score,
        diff: subjScore - objSleepRow.sleep_score
      };
    }).filter((x): x is {date:string, subj:number, obj:number, diff:number} => x !== null);

  $: avgSleepGap = avg(sleepGapList.map(x => Math.abs(x.diff)));
  $: sleepGapDirection = avg(sleepGapList.map(x => x.diff)); // positive = subjective higher than objective

  // -- Garmin Metrics vs Mood --
  $: daysWithHighSteps = stepsRows.filter(r => Number(r.total_steps) >= 10000).map(r => String(r.date));
  $: daysWithLowStress = stressRows.filter(r => Number(r.overall_stress_level) < 25).map(r => String(r.date));
  $: daysWithHighStepsMood = avgOfNullable(entries.filter(e => daysWithHighSteps.includes(String(e.timestamp).split('T')[0])).map(e => e.mood_score));
  $: daysWithLowStressMood = avgOfNullable(entries.filter(e => daysWithLowStress.includes(String(e.timestamp).split('T')[0])).map(e => e.mood_score));

  // -- Dosage Impact (Coffee example) --
  // We look for activities named "Coffee" or similar and group by quantity.
"""
content = content.replace("  // ── Correlations & Insights Computed Properties ───────────────────────────", "  // ── Correlations & Insights Computed Properties ───────────────────────────\n" + new_computed)

# Append to UI
new_ui = """
      <!-- Subjective vs Objective Sleep -->
      <article class="insight-card">
        <h4>Subjective vs Garmin Sleep</h4>
        <p class="insight-desc">Do you feel as rested as Garmin says?</p>
        <div style="margin-top: 1rem;">
          {#if sleepGapList.length > 0}
            <p><strong>Average Gap:</strong> {avgSleepGap?.toFixed(1)} points</p>
            <p style="font-size: 0.9rem; color: var(--color-neutral-text-muted);">
              {sleepGapDirection! > 0 ? "You typically feel MORE rested than Garmin thinks." : "You typically feel LESS rested than Garmin thinks."}
            </p>
            <div style="display: flex; gap: 4px; margin-top: 0.5rem; height: 40px; align-items: flex-end;">
              {#each sleepGapList.slice(-20) as day}
                <div style="flex: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 1px;">
                  <div style="background: #10b981; height: {day.subj}%; border-radius: 2px;" title="Subj: {day.subj.toFixed(0)}"></div>
                  <div style="background: #3b82f6; height: {day.obj}%; border-radius: 2px;" title="Garmin: {day.obj}"></div>
                </div>
              {/each}
            </div>
            <p style="font-size: 0.7rem; color: #999; margin-top: 4px; text-align: center;">Last {Math.min(20, sleepGapList.length)} logged days (Green=Subjective, Blue=Garmin)</p>
          {:else}
            <p style="color: #999;">Not enough subjective sleep ratings to compare.</p>
          {/if}
        </div>
      </article>

      <!-- Garmin vs Mood -->
      <article class="insight-card">
        <h4>Garmin vs Subjective Mood</h4>
        <p class="insight-desc">How objective health impacts mood (lower mood score is better)</p>
        <div style="margin-top: 1rem; display: flex; flex-direction: column; gap: 0.8rem;">
          <div>
            <strong>Days >10k Steps:</strong> 
            <span>{daysWithHighStepsMood ? daysWithHighStepsMood.toFixed(2) : 'N/A'} avg mood</span>
          </div>
          <div>
            <strong>Days &lt;25 Stress:</strong> 
            <span>{daysWithLowStressMood ? daysWithLowStressMood.toFixed(2) : 'N/A'} avg mood</span>
          </div>
          <div style="font-size: 0.8rem; color: #999; margin-top: 0.5rem;">
            Baseline avg mood: {avgMood ? avgMood.toFixed(2) : 'N/A'}
          </div>
        </div>
      </article>
"""
content = content.replace("      <!-- Influence on Mood -->", new_ui + "\n      <!-- Influence on Mood -->")

with open('frontend-web/src/routes/analytics/+page.svelte', 'w') as f:
    f.write(content)
