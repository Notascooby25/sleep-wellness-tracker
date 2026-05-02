<script lang="ts">
  const today = new Date().toISOString().slice(0, 10);
  const thirtyDaysAgo = new Date(Date.now() - 29 * 86400000).toISOString().slice(0, 10);

  const sourceOptions = [
    { value: 'sleep', label: 'Sleep' },
    { value: 'hrv', label: 'HRV' },
    { value: 'stress', label: 'Stress' },
    { value: 'body_battery', label: 'Body Battery' },
    { value: 'rhr', label: 'Resting Heart Rate' },
    { value: 'hydration', label: 'Hydration' },
    { value: 'steps', label: 'Steps' },
    { value: 'mood', label: 'Mood Log' },
    { value: 'activities', label: 'Garmin Activities' }
  ];

  let startDate = thirtyDaysAgo;
  let endDate = today;
  let selected = new Set<string>(['sleep', 'hrv', 'stress', 'body_battery', 'steps']);
  let busy = false;
  let status = '';

  const toggleSource = (value: string) => {
    if (selected.has(value)) {
      selected.delete(value);
    } else {
      selected.add(value);
    }
    selected = new Set(selected);
  };

  const exportCsv = async () => {
    status = '';
    if (!startDate || !endDate) {
      status = 'Please choose both start and end dates.';
      return;
    }
    if (endDate < startDate) {
      status = 'End date must be on or after start date.';
      return;
    }
    if (selected.size === 0) {
      status = 'Select at least one data source.';
      return;
    }

    busy = true;
    try {
      const params = new URLSearchParams({
        sources: Array.from(selected).join(','),
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(`/api/export/csv?${params.toString()}`);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = `export_${startDate}_${endDate}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);

      status = 'Export downloaded successfully.';
    } catch (error) {
      status = `Export failed: ${error}`;
    } finally {
      busy = false;
    }
  };
</script>

<section class="hero">
  <h2>Export Data to CSV</h2>
  <p>Select a date range and one or more data sources to download a merged CSV export.</p>
</section>

<section class="card export-card">
  <div class="grid two">
    <label>
      <div class="label">From</div>
      <input type="date" bind:value={startDate} />
    </label>
    <label>
      <div class="label">To</div>
      <input type="date" bind:value={endDate} />
    </label>
  </div>

  <div class="label block-gap">Data Sources</div>
  <div class="source-grid">
    {#each sourceOptions as source}
      <label class="source-item">
        <input
          type="checkbox"
          checked={selected.has(source.value)}
          on:change={() => toggleSource(source.value)}
        />
        <span>{source.label}</span>
      </label>
    {/each}
  </div>

  <div class="actions">
    <button class="btn-primary" disabled={busy} on:click={exportCsv}>
      {busy ? 'Exporting...' : 'Export CSV'}
    </button>
  </div>

  {#if status}
    <p class="status-msg">{status}</p>
  {/if}
</section>

<style>
  .export-card { padding: 1rem; }
  .block-gap { margin-top: 0.9rem; }
  .source-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }
  .source-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    border: 1px solid #d7e6f7;
    border-radius: 10px;
    background: #f8fbff;
    padding: 0.55rem 0.65rem;
    color: #1e4b76;
    font-size: 0.9rem;
  }
  .source-item input { width: auto; }
  .actions {
    margin-top: 1rem;
    display: flex;
    justify-content: center;
  }
  .btn-primary {
    background: #3c79c5;
    border-color: #3168ad;
    color: #fff;
    min-width: 170px;
    font-weight: 700;
  }
  .status-msg {
    margin-top: 0.75rem;
    font-size: 0.9rem;
    color: #22543d;
    background: #d4edda;
    border-radius: 8px;
    padding: 0.4rem 0.6rem;
  }

  @media (max-width: 860px) {
    .source-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }

  @media (max-width: 540px) {
    .source-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
