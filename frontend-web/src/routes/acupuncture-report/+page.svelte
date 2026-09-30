<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson } from '$lib/api';

  let sessions: string[] = [];
  let startDate: string = '';
  let endDate: string = '';
  
  let allActivities: string[] = [];
  let excludeActivities: string[] = ['Acupuncture', 'Eye Mask'];
  let excludeInput = '';
  
  let summary: any = null;
  let loading = true;
  let error = '';

  const loadInitial = async () => {
    try {
      const [sessRes, actRes] = await Promise.all([
        getJson<{ sessions: string[] }>('/reports/acupuncture-sessions'),
        getJson<any[]>('/activities/')
      ]);
      sessions = sessRes?.sessions || [];
      allActivities = actRes ? actRes.map(a => a.name).filter(Boolean).sort() : [];
      
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
      error = "Failed to load initial data.";
    }
  };

  const loadSummary = async () => {
    loading = true;
    try {
      const excludes = excludeActivities.map(a => `exclude_activities=${encodeURIComponent(a)}`).join('&');
      const query = `?start_date=${startDate}&end_date=${endDate}${excludes ? '&' + excludes : ''}`;
      summary = await getJson<any>(`/reports/headache-summary${query}`);
    } catch (err) {
      error = "Failed to load summary.";
    } finally {
      loading = false;
    }
  };

  const addExclude = () => {
    if (excludeInput && !excludeActivities.includes(excludeInput)) {
      excludeActivities = [...excludeActivities, excludeInput];
      localStorage.setItem('headache_exclude_activities', JSON.stringify(excludeActivities));
      excludeInput = '';
      loadSummary();
    }
  };

  const removeExclude = (act: string) => {
    excludeActivities = excludeActivities.filter(a => a !== act);
    localStorage.setItem('headache_exclude_activities', JSON.stringify(excludeActivities));
    loadSummary();
  };

  onMount(() => {
    const saved = localStorage.getItem('headache_exclude_activities');
    if (saved) {
      try {
        excludeActivities = JSON.parse(saved);
      } catch (e) {}
    }
    loadInitial();
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

  {#if summary.biometrics && summary.biometrics.length > 0}
  <section class="card">
    <h3>Contributing Biometrics (Garmin)</h3>
    <p style="font-size: 0.9rem; color: #666; margin-top: -0.5rem; margin-bottom: 1rem;">
      These physical metrics showed a significant difference on headache days.
    </p>
    <table style="width: 100%; text-align: left; border-collapse: collapse;">
      <thead>
        <tr style="border-bottom: 1px solid #ddd;">
          <th style="padding: 0.5rem;">Metric</th>
          <th style="padding: 0.5rem;">On Symptom Days</th>
          <th style="padding: 0.5rem;">On Clean Days</th>
        </tr>
      </thead>
      <tbody>
        {#each summary.biometrics as bio}
          <tr style="border-bottom: 1px solid #eee;">
            <td style="padding: 0.5rem; font-weight: bold;">{bio.metric}</td>
            <td style="padding: 0.5rem; color: #b42318;">{bio.symptom_avg}</td>
            <td style="padding: 0.5rem; color: #086c3a;">{bio.clean_avg}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
  {/if}

  <section class="card">
    <h3>Potential Activity Triggers</h3>
    <p style="font-size: 0.9rem; color: #666; margin-top: -0.5rem; margin-bottom: 1rem;">
      These activities occurred significantly more often on days you had a headache/migraine.
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

<section class="card filters">
  <h3>Exclude Activities</h3>
  <p style="font-size: 0.85rem; color: #666; margin-top: -0.5rem; margin-bottom: 1rem;">
    Ignore activities that have no bearing on headaches (e.g. Eye Mask, Earplugs).
  </p>
  
  <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
    <select bind:value={excludeInput} style="flex: 1;">
      <option value="">Select an activity to exclude...</option>
      {#each allActivities as act}
        {#if !excludeActivities.includes(act)}
          <option value={act}>{act}</option>
        {/if}
      {/each}
    </select>
    <button on:click={addExclude} class="btn-primary" style="padding: 0 1rem; border-radius: 4px; background: #3c79c5; color: white; border: none;">Add</button>
  </div>

  <div class="pills">
    {#each excludeActivities as exc}
      <span class="pill" on:click={() => removeExclude(exc)} role="button" tabindex="0" on:keydown={(e) => { if (e.key === 'Enter') removeExclude(exc); }}>
        {exc} &times;
      </span>
    {/each}
  </div>
</section>

<style>
  .filters { background: #f9fbff; }
  .stats { display: flex; gap: 1rem; flex-wrap: wrap; }
  .stat-box { flex: 1; min-width: 100px; background: #fff; border: 1px solid #e0e7ff; padding: 1rem; border-radius: 8px; text-align: center; }
  .stat-value { font-size: 2rem; font-weight: 800; color: #1e4b76; }
  .stat-label { font-size: 0.8rem; font-weight: 600; color: #496685; text-transform: uppercase; margin-top: 0.5rem; }
  table th { font-size: 0.8rem; color: #8091a7; text-transform: uppercase; }
  
  .pills { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .pill { background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.2rem 0.6rem; font-size: 0.8rem; color: #1e4b76; cursor: pointer; }
  .pill:hover { background: #fee4e2; border-color: #fca5a5; color: #b42318; }
</style>
