<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';

  let sessions: string[] = [];
  let startDate: string = '';
  let endDate: string = '';
  let summary: any = null;
  let loading = true;
  let error = '';

  const loadSessions = async () => {
    try {
      const res = await getJson<{ sessions: string[] }>('/reports/acupuncture-sessions');
      sessions = res?.sessions || [];
      if (sessions.length > 0) {
        // Set default to day after last session
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
      error = "Failed to load sessions.";
    }
  };

  const loadSummary = async () => {
    loading = true;
    try {
      const query = `?start_date=${startDate}&end_date=${endDate}`;
      summary = await getJson<any>(`/reports/headache-summary${query}`);
    } catch (err) {
      error = "Failed to load summary.";
    } finally {
      loading = false;
    }
  };

  onMount(() => {
    loadSessions();
  });
</script>

<section class="hero">
  <h2>Acupuncture & Symptom Report</h2>
  <p>Track headache/migraine frequency and potential triggers over time.</p>
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
</section>

{#if loading}
  <p style="text-align:center;">Loading report...</p>
{:else if error}
  <p style="text-align:center; color: red;">{error}</p>
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
      <div class="stat-value">{Math.round((summary.symptom_days / summary.total_days) * 100) || 0}%</div>
      <div class="stat-label">Frequency</div>
    </div>
    {#if summary.average_severity}
      <div class="stat-box">
        <div class="stat-value">{summary.average_severity}</div>
        <div class="stat-label">Avg Severity</div>
      </div>
    {/if}
  </section>

  <section class="card">
    <h3>Potential Triggers</h3>
    <p style="font-size: 0.9rem; color: #666; margin-top: -0.5rem; margin-bottom: 1rem;">
      These activities occurred significantly more often on days you had a headache/migraine compared to symptom-free days.
    </p>
    
    {#if summary.triggers && summary.triggers.length > 0}
      <table style="width: 100%; text-align: left; border-collapse: collapse;">
        <thead>
          <tr style="border-bottom: 1px solid #ddd;">
            <th style="padding: 0.5rem;">Activity</th>
            <th style="padding: 0.5rem;">On Symptom Days</th>
            <th style="padding: 0.5rem;">On Clean Days</th>
          </tr>
        </thead>
        <tbody>
          {#each summary.triggers as trigger}
            <tr style="border-bottom: 1px solid #eee;">
              <td style="padding: 0.5rem; font-weight: bold;">{trigger.activity}</td>
              <td style="padding: 0.5rem; color: #b42318;">{trigger.symptom_freq}%</td>
              <td style="padding: 0.5rem; color: #086c3a;">{trigger.clean_freq}%</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <p style="text-align: center; color: #888;">Not enough data to identify clear triggers for this period.</p>
    {/if}
  </section>
{/if}

<style>
  .filters { background: #f9fbff; }
  .stats { display: flex; gap: 1rem; flex-wrap: wrap; }
  .stat-box { flex: 1; min-width: 100px; background: #fff; border: 1px solid #e0e7ff; padding: 1rem; border-radius: 8px; text-align: center; }
  .stat-value { font-size: 2rem; font-weight: 800; color: #1e4b76; }
  .stat-label { font-size: 0.8rem; font-weight: 600; color: #496685; text-transform: uppercase; margin-top: 0.5rem; }
  table th { font-size: 0.8rem; color: #8091a7; text-transform: uppercase; }
</style>
