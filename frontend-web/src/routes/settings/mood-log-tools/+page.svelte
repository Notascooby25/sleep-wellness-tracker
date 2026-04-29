<script lang="ts">
  import { onMount } from 'svelte';
  import { deleteJson, getJson, postJson, putJson } from '$lib/api';
  import type { Activity, Category, MoodEntry } from '$lib/types';

  type ImportRow = {
    mood_score: number | null;
    notes: string | null;
    timestamp: string;
    activity_ids: number[];
  };

  type BackupPayload = {
    version: string;
    exported_at: string;
    timezone: string;
    entries: MoodEntry[];
    activities: Activity[];
    categories: Category[];
  };

  let entries: MoodEntry[] = [];
  let activities: Activity[] = [];
  let categories: Category[] = [];

  let busy = false;
  let status = '';

  let selectedFile: File | null = null;

  let deleteDate = new Date().toISOString().slice(0, 10);
  let confirmDeleteAll = false;
  let confirmDeleteDay = false;

  let cleanupCategoryIds: number[] = [];
  let includeMixed = false;
  let previewOpen = false;
  let matches: MoodEntry[] = [];
  let dryRun = true;

  let importSummary = '';

  const dateFmtUk = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' });

  const toUkDate = (timestamp: string): string => dateFmtUk.format(new Date(timestamp));

  const csvEscape = (value: string): string => {
    if (value.includes('"') || value.includes(',') || value.includes('\n')) {
      return `"${value.replaceAll('"', '""')}"`;
    }
    return value;
  };

  const downloadText = (filename: string, mime: string, content: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  };

  const signatureOf = (row: ImportRow | MoodEntry): string => {
    const activityIds = (row.activity_ids || [])
      .map((n: number) => Number(n))
      .filter((n: number) => Number.isFinite(n))
      .sort((a: number, b: number) => a - b)
      .join(',');
    const mood = row.mood_score === null || row.mood_score === undefined ? '' : String(row.mood_score);
    const notes = (row.notes || '').trim();
    return `${row.timestamp}|${mood}|${notes}|${activityIds}`;
  };

  const parseActivityIds = (value: unknown): number[] => {
    if (Array.isArray(value)) {
      return value.map(Number).filter((n) => Number.isFinite(n));
    }
    if (typeof value !== 'string') return [];
    const text = value.trim();
    if (!text) return [];

    try {
      const parsed = JSON.parse(text);
      if (Array.isArray(parsed)) {
        return parsed.map(Number).filter((n) => Number.isFinite(n));
      }
    } catch {
      // Not JSON array, continue with comma split.
    }

    return text
      .split(',')
      .map((x) => Number(x.trim()))
      .filter((n) => Number.isFinite(n));
  };

  const normalizeImportRow = (row: Record<string, unknown>): ImportRow => {
    const moodRaw = row.mood_score ?? row.rating ?? null;
    const moodNum = moodRaw === null || moodRaw === '' ? null : Number(moodRaw);

    return {
      mood_score: Number.isFinite(moodNum as number) ? (moodNum as number) : null,
      notes: (row.notes ?? row.note ?? null) as string | null,
      timestamp: String(row.timestamp ?? ''),
      activity_ids: parseActivityIds(row.activity_ids ?? row.activities ?? [])
    };
  };

  const isoTimestamp = (value: string): string => {
    const ts = (value || '').trim();
    if (!ts) return '';
    const d = new Date(ts);
    if (Number.isNaN(d.getTime())) return '';
    return d.toISOString();
  };

  const parseCsv = (text: string): Record<string, unknown>[] => {
    const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
    if (lines.length < 2) return [];

    const splitLine = (line: string): string[] => {
      const out: string[] = [];
      let cur = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if (ch === '"') {
          if (inQuotes && line[i + 1] === '"') {
            cur += '"';
            i += 1;
          } else {
            inQuotes = !inQuotes;
          }
        } else if (ch === ',' && !inQuotes) {
          out.push(cur);
          cur = '';
        } else {
          cur += ch;
        }
      }
      out.push(cur);
      return out;
    };

    const headers = splitLine(lines[0]).map((h) => h.trim());
    const rows: Record<string, unknown>[] = [];

    for (let i = 1; i < lines.length; i += 1) {
      const values = splitLine(lines[i]);
      const row: Record<string, unknown> = {};
      headers.forEach((h, idx) => {
        row[h] = values[idx] ?? '';
      });
      rows.push(row);
    }

    return rows;
  };

  const load = async () => {
    busy = true;
    status = '';
    try {
      const [rows, acts, cats] = await Promise.all([
        getJson<MoodEntry[]>('/mood/'),
        getJson<Activity[]>('/activities/'),
        getJson<Category[]>('/categories/')
      ]);
      entries = rows;
      activities = acts;
      categories = cats;

      if (cleanupCategoryIds.length === 0) {
        const defaults = ['Lifestyle', 'Before Sleep', 'During Sleep'];
        cleanupCategoryIds = categories
          .filter((c) => defaults.includes(c.name))
          .map((c) => c.id);
      }
    } catch (error) {
      status = `Load failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  const handleFileChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null;
    const files = input?.files;
    selectedFile = files && files.length > 0 ? files[0] : null;
  };

  const handleCategoryChange = (event: Event) => {
    const select = event.currentTarget as HTMLSelectElement | null;
    if (!select) return;
    cleanupCategoryIds = Array.from(select.selectedOptions).map((o) => Number(o.value));
  };

  const exportJson = (): string => {
    return JSON.stringify({ entries }, null, 2);
  };

  const exportBackup = (): string => {
    const payload: BackupPayload = {
      version: 'mood-backup-v1',
      exported_at: new Date().toISOString(),
      timezone: 'Europe/London',
      entries,
      activities,
      categories
    };
    return JSON.stringify(payload, null, 2);
  };

  const exportCsv = (): string => {
    const header = ['timestamp', 'mood_score', 'notes', 'activity_ids'];
    const body = entries.map((e) => {
      const notes = e.notes || '';
      const activityIds = JSON.stringify(e.activity_ids || []);
      return [e.timestamp, e.mood_score === null ? '' : String(e.mood_score), notes, activityIds]
        .map(csvEscape)
        .join(',');
    });
    return [header.join(','), ...body].join('\n');
  };

  const exportJsonFile = () => {
    const stamp = new Date().toISOString().slice(0, 19).replaceAll(':', '').replace('T', '_');
    downloadText(`mood_log_export_${stamp}.json`, 'application/json;charset=utf-8', exportJson());
    status = 'JSON export downloaded.';
  };

  const exportCsvFile = () => {
    const stamp = new Date().toISOString().slice(0, 19).replaceAll(':', '').replace('T', '_');
    downloadText(`mood_log_export_${stamp}.csv`, 'text/csv;charset=utf-8', exportCsv());
    status = 'CSV export downloaded.';
  };

  const exportBackupFile = () => {
    const stamp = new Date().toISOString().slice(0, 19).replaceAll(':', '').replace('T', '_');
    downloadText(`mood_log_backup_${stamp}.json`, 'application/json;charset=utf-8', exportBackup());
    status = 'Full backup downloaded.';
  };

  const importEntries = async () => {
    if (!selectedFile) return;

    status = '';
    busy = true;
    try {
      const text = await selectedFile.text();
      const ext = selectedFile.name.toLowerCase();

      let rows: Record<string, unknown>[] = [];
      let backupActivityNamesById = new Map<number, string>();
      if (ext.endsWith('.json')) {
        const obj = JSON.parse(text);
        if (Array.isArray(obj)) {
          rows = obj as Record<string, unknown>[];
        } else if (obj && typeof obj === 'object' && Array.isArray((obj as { entries?: unknown }).entries)) {
          rows = (obj as { entries: Record<string, unknown>[] }).entries;
          const backupActivities = (obj as { activities?: Activity[] }).activities || [];
          backupActivityNamesById = new Map(
            backupActivities
              .filter((a) => a?.id !== undefined && !!a?.name)
              .map((a) => [Number(a.id), String(a.name)])
          );
        } else {
          throw new Error('JSON must be an array or an object with an entries array');
        }
      } else if (ext.endsWith('.csv')) {
        rows = parseCsv(text);
      } else {
        throw new Error('Only JSON and CSV are supported');
      }

      const localActivityIdByName = new Map(
        activities
          .filter((a) => a?.id !== undefined && !!a?.name)
          .map((a) => [String(a.name).trim().toLowerCase(), Number(a.id)])
      );

      let remappedActivities = 0;
      const toImport = rows
        .map((row) => normalizeImportRow(row))
        .map((row) => {
          const ts = isoTimestamp(row.timestamp);
          if (!ts) return { ...row, timestamp: '' };

          const mappedIds: number[] = [];
          for (const aid of row.activity_ids) {
            if (activities.some((a) => a.id === aid)) {
              mappedIds.push(aid);
              continue;
            }
            const backupName = backupActivityNamesById.get(aid);
            if (!backupName) continue;
            const localId = localActivityIdByName.get(backupName.trim().toLowerCase());
            if (localId !== undefined) {
              mappedIds.push(localId);
              remappedActivities += 1;
            }
          }

          return {
            ...row,
            timestamp: ts,
            activity_ids: Array.from(new Set(mappedIds))
          };
        })
        .filter((row) => row.timestamp.trim().length > 0);

      const existing = new Set(entries.map((e) => signatureOf(e)));
      const seen = new Set<string>();

      let imported = 0;
      let failed = 0;
      let skipped = 0;

      for (const row of toImport) {
        const sig = signatureOf(row);
        if (existing.has(sig) || seen.has(sig)) {
          skipped += 1;
          continue;
        }

        try {
          if (dryRun) {
            imported += 1;
            existing.add(sig);
            seen.add(sig);
            continue;
          }
          await postJson('/mood/', row);
          imported += 1;
          existing.add(sig);
          seen.add(sig);
        } catch {
          failed += 1;
        }
      }

      if (!dryRun) {
        await load();
      }
      importSummary = `Checked ${toImport.length} rows: ${imported} ready/imported, ${skipped} duplicates skipped, ${failed} failed, ${remappedActivities} activity IDs remapped.`;
      status = dryRun
        ? 'Dry run finished. Disable dry run and import again to apply changes.'
        : `Import complete: ${imported} imported, ${skipped} duplicates skipped, ${failed} failed.`;
    } catch (error) {
      status = `Import failed: ${error}`;
      importSummary = '';
    } finally {
      busy = false;
    }
  };

  const entriesOnDate = (date: string): MoodEntry[] => entries.filter((e) => toUkDate(e.timestamp) === date);

  const deleteRows = async (rows: MoodEntry[]) => {
    if (rows.length === 0) {
      status = 'No matching entries to delete.';
      return;
    }

    busy = true;
    status = '';
    let deleted = 0;
    let failed = 0;

    for (const row of rows) {
      if (row.id === undefined) continue;
      try {
        await deleteJson(`/mood/${row.id}`);
        deleted += 1;
      } catch {
        failed += 1;
      }
    }

    await load();
    status = `Bulk delete complete: ${deleted} deleted, ${failed} failed.`;
    busy = false;
  };

  const activityById = () => new Map(activities.map((a) => [a.id, a]));
  const categoryNameById = () => new Map(categories.map((c) => [c.id, c.name]));

  const rowCategoryNames = (row: MoodEntry): string[] => {
    const actMap = activityById();
    const catMap = categoryNameById();
    const categoryIds = new Set<number>();

    for (const id of row.activity_ids || []) {
      const cid = actMap.get(id)?.category_id;
      if (cid !== undefined && cid !== null) {
        categoryIds.add(cid);
      }
    }

    return Array.from(categoryIds).map((cid) => catMap.get(cid) || '(uncategorized)');
  };

  const cleanupMatches = (): MoodEntry[] => {
    const target = new Set(cleanupCategoryIds);
    if (target.size === 0) return [];

    const actMap = activityById();

    return entries.filter((entry) => {
      if (entry.mood_score === null || entry.mood_score === undefined) return false;
      const activityIds = entry.activity_ids || [];
      if (activityIds.length === 0) return false;

      const cats = new Set<number>();
      for (const aid of activityIds) {
        const cid = actMap.get(aid)?.category_id;
        if (cid !== undefined && cid !== null) cats.add(cid);
      }
      if (cats.size === 0) return false;

      if (includeMixed) {
        for (const cid of cats) {
          if (target.has(cid)) return true;
        }
        return false;
      }

      for (const cid of cats) {
        if (!target.has(cid)) return false;
      }
      return true;
    });
  };

  const clearRatings = async () => {
    const matches = cleanupMatches();
    if (matches.length === 0) {
      status = 'No matching rated entries found.';
      return;
    }

    busy = true;
    status = '';
    let updated = 0;
    let failed = 0;

    for (const row of matches) {
      if (row.id === undefined) continue;
      try {
        await putJson(`/mood/${row.id}`, {
          mood_score: null,
          notes: row.notes || null,
          timestamp: row.timestamp,
          activity_ids: row.activity_ids || []
        });
        updated += 1;
      } catch {
        failed += 1;
      }
    }

    await load();
    status = `Rating cleanup complete: ${updated} updated, ${failed} failed.`;
    busy = false;
  };

  $: matches = cleanupMatches();

  onMount(load);
</script>

<section class="hero">
  <h2>Mood Log Tools</h2>
  <p>Export, backup, restore, and run bulk maintenance tools for your mood log.</p>
</section>

<section class="card">
  <div style="display:flex; justify-content:space-between; align-items:center; gap:0.6rem;">
    <h3 style="margin:0;">Settings</h3>
    <button on:click={load} disabled={busy}>{busy ? 'Working...' : 'Refresh'}</button>
  </div>
  <p class="label" style="margin-top:0.45rem;">Loaded {entries.length} entries</p>
  {#if status}
    <p>{status}</p>
  {/if}
</section>

<section class="card">
  <h3>Export and Backup</h3>
  <div style="display:flex; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.6rem;">
    <button on:click={exportJsonFile} disabled={busy || entries.length === 0}>Export JSON</button>
    <button on:click={exportCsvFile} disabled={busy || entries.length === 0}>Export CSV</button>
    <button on:click={exportBackupFile} disabled={busy || entries.length === 0}>Export Full Backup</button>
  </div>
  <p class="label" style="margin-top:0;">
    Full backup includes entries, activities, categories, and metadata. Use this for migration/reinstall recovery.
  </p>
</section>

<section class="card">
  <h3>Import and Restore</h3>

  <div class="label">Import mood log (JSON or CSV)</div>
  <input
    type="file"
    accept=".json,.csv,application/json,text/csv"
    on:change={handleFileChange}
  />
  {#if selectedFile}
    <p class="label" style="margin:0.45rem 0 0;">Selected: {selectedFile.name}</p>
  {/if}
  <label style="display:flex; gap:0.4rem; align-items:center; margin-top:0.55rem;">
    <input type="checkbox" bind:checked={dryRun} style="width:auto;" />
    <span>Dry run first (validate and count only, no writes)</span>
  </label>
  <div style="margin-top:0.5rem;">
    <button on:click={importEntries} disabled={!selectedFile || busy}>
      {dryRun ? 'Validate Import' : 'Run Import'}
    </button>
  </div>
  {#if importSummary}
    <p class="label" style="margin-top:0.55rem;">{importSummary}</p>
  {/if}
</section>

<section class="card">
  <h3>Bulk Delete</h3>
  <label>
    <div class="label">Delete entries for date</div>
    <input type="date" bind:value={deleteDate} />
  </label>

  <div style="display:flex; gap:0.5rem; margin-top:0.6rem; flex-wrap:wrap;">
    <button on:click={() => (confirmDeleteDay = true)} disabled={busy}>Delete Selected Day</button>
    <button on:click={() => (confirmDeleteAll = true)} disabled={busy}>Delete All Entries</button>
  </div>

  {#if confirmDeleteDay}
    <p>Delete all entries on {deleteDate}? This cannot be undone.</p>
    <div style="display:flex; gap:0.5rem;">
      <button
        on:click={async () => {
          confirmDeleteDay = false;
          await deleteRows(entriesOnDate(deleteDate));
        }}
      >
        Confirm Bulk Delete
      </button>
      <button on:click={() => (confirmDeleteDay = false)}>Cancel Bulk Delete</button>
    </div>
  {/if}

  {#if confirmDeleteAll}
    <p>Delete all mood log entries? This cannot be undone.</p>
    <div style="display:flex; gap:0.5rem;">
      <button
        on:click={async () => {
          confirmDeleteAll = false;
          await deleteRows(entries);
        }}
      >
        Confirm Bulk Delete
      </button>
      <button on:click={() => (confirmDeleteAll = false)}>Cancel Bulk Delete</button>
    </div>
  {/if}
</section>

<section class="card">
  <h3>Bulk Rating Cleanup</h3>
  <label>
    <div class="label">Categories to disassociate rating from</div>
    <select
      multiple
      size="6"
      on:change={handleCategoryChange}
    >
      {#each categories as category}
        <option value={category.id} selected={cleanupCategoryIds.includes(category.id)}>{category.name}</option>
      {/each}
    </select>
  </label>

  <label style="display:flex; gap:0.4rem; align-items:center; margin-top:0.55rem;">
    <input type="checkbox" bind:checked={includeMixed} style="width:auto;" />
    <span>Include entries that also contain other categories</span>
  </label>

  <p class="label" style="margin-top:0.55rem;">Matches with rating to clear: {matches.length}</p>

  <button on:click={() => (previewOpen = !previewOpen)} style="margin-bottom:0.5rem;">
    {previewOpen ? 'Hide matching entries' : 'Preview matching entries'}
  </button>

  {#if previewOpen}
    <div class="card" style="max-height:280px; overflow:auto;">
      {#if matches.length === 0}
        <p class="label">No matching rated entries found.</p>
      {:else}
        {#each matches.slice(0, 50) as row}
          {@const rowCats = rowCategoryNames(row)}
          <p style="margin:0 0 0.35rem;">
            #{row.id} · {new Date(row.timestamp).toLocaleString('en-GB', { hour12: false })} · Mood {row.mood_score} · Categories: {rowCats.join(', ')}
          </p>
        {/each}
        {#if matches.length > 50}
          <p class="label">Showing first 50 of {matches.length} matches.</p>
        {/if}
      {/if}
    </div>
  {/if}

  <div style="margin-top:0.6rem;">
    <button on:click={clearRatings} disabled={matches.length === 0 || busy}>Clear Ratings for Matches</button>
  </div>
</section>
