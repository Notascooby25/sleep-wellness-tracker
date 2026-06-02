<script lang="ts">
  import { onMount } from 'svelte';
  import { getJson, postJson } from '$lib/api';
  import type { Activity, Category, GarminLatestWrap, MoodEntry } from '$lib/types';

  type SleepLatest = {
    date: string;
    total_sleep_minutes?: number;
    sleep_score?: number;
  };

  type BatteryLatest = {
    date: string;
    morning_value?: number;
    end_of_day_value?: number;
  };

  type HrvLatest = {
    date: string;
    weekly_avg?: number;
    baseline_low?: number;
    baseline_high?: number;
  };

  type StressLatest = {
    date: string;
    overall_stress_level?: number;
  };

  type ImageUploadResponse = {
    image_url: string;
  };

  const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
  const MAX_IMAGE_DIMENSION = 1920;
  const JPEG_QUALITY_STEPS = [0.82, 0.74, 0.66, 0.58];
  const RESIZE_STEPS = [1, 0.85, 0.7];

  let categories: Category[] = [];
  let activities: Activity[] = [];
  let selected = new Set<number>();
  let notes = '';
  let moodScore = 3;
  // Derive both date and time from the same local instant to avoid UTC/local mismatch.
  const now = new Date();
  const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString();
  let date = localIso.slice(0, 10);
  let time = localIso.slice(11, 16);
  let status = '';
  let busy = false;
  let latestSleep: SleepLatest | null = null;
  let latestBattery: BatteryLatest | null = null;
  let latestHrv: HrvLatest | null = null;
  let latestStress: StressLatest | null = null;
  let activeCategory = 0;
  let currentStreakDays = 0;
  let imageUrl: string | null = null;
  let imageUploadBusy = false;
  let galleryInputEl: HTMLInputElement | null = null;
  let cameraInputEl: HTMLInputElement | null = null;

  const fmtMinutes = (value?: number) => {
    if (value === undefined || value === null) return '-';
    return `${Math.floor(value / 60)}h ${String(value % 60).padStart(2, '0')}m`;
  };

  const byCategory = (catId: number) => activities.filter((a) => a.category_id === catId);

  const toLocalDateKey = (isoTs: string) => {
    const d = new Date(isoTs);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  };

  const shiftDate = (isoDate: string, delta: number) => {
    const d = new Date(isoDate + 'T12:00:00');
    d.setDate(d.getDate() + delta);
    return d.toISOString().slice(0, 10);
  };

  const computeMoodStreak = (rows: MoodEntry[]) => {
    const uniqueDays = new Set(rows.map((r) => toLocalDateKey(r.timestamp)));
    const todayKey = toLocalDateKey(new Date().toISOString());
    let cursor = uniqueDays.has(todayKey) ? todayKey : shiftDate(todayKey, -1);
    if (!uniqueDays.has(cursor)) return 0;

    let streak = 0;
    while (uniqueDays.has(cursor)) {
      streak += 1;
      cursor = shiftDate(cursor, -1);
    }
    return streak;
  };

  const ratingRequired = () => {
    for (const id of selected) {
      const act = activities.find((a) => a.id === id);
      if (!act) continue;
      const cat = categories.find((c) => c.id === act.category_id);
      if (!cat) continue;
      if ((cat.require_rating ?? 1) === 1) return true;
    }
    return selected.size === 0;
  };

  const toggle = (id: number) => {
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    selected = new Set(selected);
  };

  const clearSelected = () => {
    selected = new Set<number>();
  };

  const openGalleryPicker = () => {
    galleryInputEl?.click();
  };

  const openCameraPicker = () => {
    cameraInputEl?.click();
  };

  const normalizeUploadName = (fileName: string) => {
    const withoutExtension = fileName.replace(/\.[^.]+$/, '');
    const safeCharactersOnly = withoutExtension.replace(/[^A-Za-z0-9._-]+/g, '-');
    const baseName = safeCharactersOnly.replace(/^-+|-+$/g, '');
    return baseName || 'upload';
  };

  const canvasToBlob = (canvas: HTMLCanvasElement, quality: number) =>
    new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) resolve(blob);
          else reject(new Error('Unable to compress the selected image.'));
        },
        'image/jpeg',
        quality
      );
    });

  const loadImageElement = (file: File) =>
    new Promise<HTMLImageElement>((resolve, reject) => {
      const objectUrl = URL.createObjectURL(file);
      const image = new Image();
      image.onload = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(image);
      };
      image.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        reject(new Error('Unable to read the selected image.'));
      };
      image.src = objectUrl;
    });

  const compressImageFile = async (file: File) => {
    const image = await loadImageElement(file);
    const sourceWidth = image.naturalWidth || image.width;
    const sourceHeight = image.naturalHeight || image.height;
    const longestSide = Math.max(sourceWidth, sourceHeight);
    const baseScale = longestSide > MAX_IMAGE_DIMENSION ? MAX_IMAGE_DIMENSION / longestSide : 1;
    let bestCandidate: File | null = null;

    for (const resizeStep of RESIZE_STEPS) {
      const scale = Math.min(1, baseScale * resizeStep);
      const width = Math.max(1, Math.round(sourceWidth * scale));
      const height = Math.max(1, Math.round(sourceHeight * scale));
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Image compression is not supported on this device.');

      context.fillStyle = '#ffffff';
      context.fillRect(0, 0, width, height);
      context.drawImage(image, 0, 0, width, height);

      for (const quality of JPEG_QUALITY_STEPS) {
        const blob = await canvasToBlob(canvas, quality);
        const candidate = new File([blob], `${normalizeUploadName(file.name)}.jpg`, {
          type: 'image/jpeg',
          lastModified: file.lastModified
        });

        if (!bestCandidate || candidate.size < bestCandidate.size) {
          bestCandidate = candidate;
        }

        if (candidate.size <= MAX_UPLOAD_BYTES) {
          return candidate;
        }
      }
    }

    return bestCandidate ?? file;
  };

  const prepareUploadFile = async (file: File) => {
    try {
      const compressed = await compressImageFile(file);
      if (file.size > MAX_UPLOAD_BYTES) {
        return compressed;
      }
      if (compressed.size < file.size) {
        return compressed;
      }
    } catch (error) {
      if (file.size > MAX_UPLOAD_BYTES) {
        throw error;
      }
    }
    return file;
  };

  const fileToImageUrl = async (file: File) => {
    const response = await fetch('/api/mood/upload-image', {
      method: 'POST',
      headers: {
        'content-type': file.type || 'application/octet-stream',
        'x-upload-filename': encodeURIComponent(file.name || 'upload.jpg')
      },
      body: file
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `Upload failed with ${response.status}`);
    }

    const data = (await response.json()) as ImageUploadResponse;
    return data.image_url;
  };

  const uploadFromInput = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;

    imageUploadBusy = true;
    status = 'Preparing image...';
    try {
      const uploadFile = await prepareUploadFile(file);
      if (uploadFile.size > MAX_UPLOAD_BYTES) {
        status = 'Image upload failed: Unable to compress below 10 MB. Please choose a smaller photo.';
        return;
      }

      imageUrl = await fileToImageUrl(uploadFile);
      status = 'Image attached.';
    } catch (error) {
      const message = String(error);
      if (message.includes('Content-length of') && message.includes('exceeds limit')) {
        status = 'Image upload failed: Upload payload exceeded server limit.';
      } else if (message.includes('Upstream backend unavailable')) {
        status = 'Image upload failed: Backend temporarily unavailable. Please retry in a few seconds.';
      } else if (message.includes('Failed to fetch')) {
        status = 'Image upload failed: Network error while uploading. Please retry with a smaller photo.';
      } else {
        status = `Image upload failed: ${error}`;
      }
    } finally {
      imageUploadBusy = false;
      input.value = '';
    }
  };

  const clearImage = () => {
    imageUrl = null;
  };

  const moodColors: Record<number, { bg: string; active: string; label: string }> = {
    1: { bg: '#c8f3d6', active: '#1f9d53', label: 'Green' },
    2: { bg: '#e6f5a7', active: '#8fae14', label: 'Green-yellow' },
    3: { bg: '#ffe991', active: '#d19b00', label: 'Yellow' },
    4: { bg: '#ffd1a4', active: '#e27a1b', label: 'Orange' },
    5: { bg: '#ffc2be', active: '#d9423a', label: 'Red' },
  };

  const load = async () => {
    try {
      const [cats, acts, sleepWrap, batteryWrap, moodRows, hrvWrap, stressWrap] = await Promise.all([
        getJson<Category[]>('/categories/'),
        getJson<Activity[]>('/activities/'),
        getJson<GarminLatestWrap<SleepLatest>>('/garmin/sleep/latest'),
        getJson<GarminLatestWrap<BatteryLatest>>('/garmin/body-battery/latest'),
        getJson<MoodEntry[]>('/mood/?limit=365&offset=0'),
        getJson<GarminLatestWrap<HrvLatest>>('/garmin/hrv/latest'),
        getJson<GarminLatestWrap<StressLatest>>('/garmin/stress/latest'),
      ]);
      categories = cats;
      activities = acts;
      latestSleep = sleepWrap?.data || null;
      latestBattery = batteryWrap?.data || null;
      latestHrv = hrvWrap?.data || null;
      latestStress = stressWrap?.data || null;
      currentStreakDays = computeMoodStreak(moodRows);
    } catch (error) {
      status = `Load error: ${error}`;
    }
  };

  const submitEntry = async () => {
    busy = true;
    status = '';
    try {
      const timestamp = new Date(`${date}T${time}:00`).toISOString();
      const payload: MoodEntry = {
        mood_score: ratingRequired() ? moodScore : null,
        notes: notes.trim() || null,
        image_url: imageUrl,
        timestamp,
        activity_ids: Array.from(selected)
      };
      await postJson('/mood/', payload);
      status = 'Entry saved.';
      notes = '';
      imageUrl = null;
      selected = new Set<number>();
    } catch (error) {
      status = `Save failed: ${error}`;
    } finally {
      busy = false;
    }
  };

  onMount(load);

  // ── Readiness score ───────────────────────────────────────────────────────
  // Weighted: 40% sleep quality, 30% HRV vs personal baseline, 30% low stress
  $: readinessScore = (() => {
    const parts: Array<{ w: number; v: number }> = [];
    if (latestSleep?.sleep_score != null) {
      parts.push({ w: 0.4, v: latestSleep.sleep_score });
    }
    if (latestHrv?.weekly_avg != null) {
      // Normalise using personal baseline band if available, else clamp 20–80 ms
      let norm: number;
      if (latestHrv.baseline_low != null && latestHrv.baseline_high != null && latestHrv.baseline_high > latestHrv.baseline_low) {
        const band = latestHrv.baseline_high - latestHrv.baseline_low;
        norm = Math.min(100, Math.max(0, ((latestHrv.weekly_avg - latestHrv.baseline_low) / band) * 100));
      } else {
        norm = Math.min(100, Math.max(0, ((latestHrv.weekly_avg - 20) / 60) * 100));
      }
      parts.push({ w: 0.3, v: norm });
    }
    if (latestStress?.overall_stress_level != null) {
      parts.push({ w: 0.3, v: 100 - latestStress.overall_stress_level });
    }
    if (!parts.length) return null;
    const totalWeight = parts.reduce((s, p) => s + p.w, 0);
    return Math.round(parts.reduce((s, p) => s + p.w * p.v, 0) / totalWeight);
  })();

  $: readinessColor = readinessScore === null ? '#8091a7'
    : readinessScore >= 70 ? '#086c3a'
    : readinessScore >= 50 ? '#854d0e'
    : '#b42318';

  $: readinessBg = readinessScore === null ? '#e8f0f9'
    : readinessScore >= 70 ? '#dcfae6'
    : readinessScore >= 50 ? '#fef3c7'
    : '#fee4e2';
</script>

<section class="hero">
  <h2>Mood Entry</h2>
  <p>Log your mood and activity context.</p>
</section>

{#if latestSleep || latestBattery || currentStreakDays >= 0}
<section class="card garmin-snap">
  <span class="snap-label">Quick snapshot</span>
  {#if latestSleep}
    <span class="snap-pill">Sleep {fmtMinutes(latestSleep.total_sleep_minutes)} · score {latestSleep.sleep_score ?? '-'}/100</span>
  {/if}
  {#if latestBattery}
    <span class="snap-pill">Body battery AM {latestBattery.morning_value ?? '-'} · EOD {latestBattery.end_of_day_value ?? '-'}</span>
  {/if}
  {#if readinessScore !== null}
    <span class="snap-pill readiness-pill" style="background:{readinessBg};border-color:{readinessColor};color:{readinessColor};">
      Readiness {readinessScore}/100
    </span>
  {/if}
  <span class="snap-pill streak-pill">Streak {currentStreakDays} {currentStreakDays === 1 ? 'day' : 'days'}</span>
</section>
{/if}

<section class="card">
  <div class="grid two">
    <label>
      <div class="label">Date</div>
      <input type="date" bind:value={date} />
    </label>
    <label>
      <div class="label">Time</div>
      <input type="time" bind:value={time} />
    </label>
  </div>

  <div style="margin-top:0.8rem;">
    <div class="label">Mood Score <small style="color:#8091a7;">(1 = great, 5 = struggling)</small></div>
    {#if ratingRequired()}
      <div class="mood-pills">
        {#each [1,2,3,4,5] as score}
          <button
            class="mood-pill"
            class:mood-pill-active={moodScore === score}
            style="--pill-bg:{moodColors[score].bg};--pill-active:{moodColors[score].active};"
            on:click={() => (moodScore = score)}
          ><span>{score}</span><small>{moodColors[score].label}</small>{moodScore === score ? ' ✓' : ''}</button>
        {/each}
      </div>
      <p class="label" style="margin-top:0.3rem;">Selected mood score: {moodScore}</p>
    {:else}
      <p class="badge-info">Rating not required for selected activities</p>
    {/if}
  </div>

  <label style="margin-top: 0.8rem; display: block;">
    <div class="label">Notes</div>
    <textarea rows="3" bind:value={notes}></textarea>
  </label>

  <div class="image-upload-wrap">
    <div class="label">Photo <small style="color:#8091a7;">(optional)</small></div>
    <div class="image-upload-actions">
      <button on:click={openCameraPicker} disabled={busy || imageUploadBusy}>Take Photo</button>
      <button on:click={openGalleryPicker} disabled={busy || imageUploadBusy}>Upload Image</button>
      {#if imageUploadBusy}
        <span class="label" style="margin:0;">Uploading...</span>
      {/if}
    </div>

    <input
      type="file"
      accept="image/*"
      capture="environment"
      bind:this={cameraInputEl}
      on:change={uploadFromInput}
      class="hidden-file-input"
    />
    <input
      type="file"
      accept="image/*"
      bind:this={galleryInputEl}
      on:change={uploadFromInput}
      class="hidden-file-input"
    />

    {#if imageUrl}
      <div class="image-preview-wrap">
        <img src={`/api${imageUrl}`} alt="Mood attachment preview" class="image-preview" />
        <button class="btn-clear" on:click={clearImage} disabled={busy || imageUploadBusy}>Remove</button>
      </div>
    {/if}
  </div>

  <div style="margin-top: 0.75rem; display: flex; gap: 0.5rem;">
    <button class="btn-primary" disabled={busy} on:click={submitEntry}>Save Entry</button>
    <button disabled={busy} on:click={load}>Refresh</button>
  </div>
  {#if status}<p class="status-msg">{status}</p>{/if}
</section>

<section class="card">
  <div class="acts-header">
    <h3 style="margin:0;">Activities</h3>
    <span class="label" style="flex:1;margin:0;">Tap chips to toggle, then switch categories using tabs.</span>
    <button class="btn-clear" on:click={clearSelected}>Clear</button>
  </div>

  {#if selected.size > 0}
    <div class="selected-summary">
      {#each Array.from(selected) as id}
        {@const act = activities.find(a => a.id === id)}
        {#if act}
          <button class="chip chip-selected" on:click={() => toggle(id)}>{act.name} ×</button>
        {/if}
      {/each}
    </div>
  {/if}

  {#if categories.length === 0}
    <p>No categories found.</p>
  {:else}
    <div class="cat-tabs">
      {#each categories as cat, i}
        <button
          class="cat-tab"
          class:cat-tab-active={activeCategory === i}
          on:click={() => (activeCategory = i)}
        >
          {cat.name}
          {#if byCategory(cat.id).some(a => selected.has(a.id))}
            <span class="cat-dot"></span>
          {/if}
        </button>
      {/each}
    </div>

    {#if categories[activeCategory]}
      {@const catActivities = byCategory(categories[activeCategory].id)}
      <div class="chips">
        {#each catActivities as activity}
          <button
            class="chip"
            class:chip-selected={selected.has(activity.id)}
            on:click={() => toggle(activity.id)}
          >{activity.name}</button>
        {:else}
          <p class="label">No activities in this category.</p>
        {/each}
      </div>
    {/if}
  {/if}
</section>

<style>
  .garmin-snap { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  .snap-label { font-size: 0.78rem; font-weight: 700; color: #496685; text-transform: uppercase; letter-spacing: 0.04em; }
  .snap-pill { background: #eef4fb; border: 1px solid #ccddf4; border-radius: 999px; padding: 0.18rem 0.55rem; font-size: 0.8rem; color: #1e4b76; }
  .readiness-pill { font-weight: 700; }
  .streak-pill { background: #fff3c4; border-color: #f4d47a; color: #6b4c03; font-weight: 700; }
  .mood-pills { display: flex; gap: 0.5rem; margin-top: 0.35rem; flex-wrap: wrap; }
  .mood-pill {
    flex: 1 1 0; min-width: 52px; max-width: 100px;
    padding: 0.55rem 0.15rem; border-radius: 14px; border: 2px solid transparent;
    background: var(--pill-bg); color: #132238;
    font-size: 1rem; font-weight: 700; cursor: pointer; transition: all 0.12s;
    display: flex; flex-direction: column; align-items: center; line-height: 1.05;
  }
  .mood-pill small { font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; opacity: 0.85; }
  .mood-pill-active {
    background: var(--pill-active) !important; border-color: var(--pill-active) !important;
    color: #fff !important; box-shadow: 0 0 0 3px rgba(0,0,0,0.08);
  }
  .mood-pill-active small { opacity: 1; }
  .badge-info { font-size: 0.84rem; color: #496685; background: #eef4fb; border: 1px solid #ccddf4; border-radius: 8px; padding: 0.35rem 0.6rem; margin-top: 0.35rem; }
  .image-upload-wrap { margin-top: 0.9rem; }
  .image-upload-actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-top: 0.35rem; }
  .hidden-file-input { position: absolute; opacity: 0; pointer-events: none; width: 0; height: 0; }
  .image-preview-wrap { margin-top: 0.55rem; display: flex; gap: 0.5rem; align-items: flex-start; flex-wrap: wrap; }
  .image-preview {
    width: min(260px, 100%);
    max-height: 260px;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid #ccddf4;
    box-shadow: 0 4px 14px rgba(12, 33, 62, 0.08);
  }
  .btn-primary { background: #3c79c5; color: #fff; border-color: #3168ad; }
  .btn-clear { background: transparent; border-color: #c7d9ef; color: #496685; font-size: 0.84rem; padding: 0.3rem 0.7rem; white-space: nowrap; }
  .status-msg { font-size: 0.88rem; color: #22543d; background: #d4edda; border-radius: 8px; padding: 0.3rem 0.6rem; margin-top: 0.4rem; }
  .acts-header { display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 0.55rem; }
  .selected-summary { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-bottom: 0.6rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e8f0f9; }
  .cat-tabs { display: flex; flex-wrap: wrap; gap: 0.3rem; border-bottom: 2px solid #e2eaf4; margin-bottom: 0.6rem; padding-bottom: 0.35rem; }
  .cat-tab { position: relative; background: transparent; border: 1px solid #d7e6f7; border-radius: 999px; padding: 0.3rem 0.65rem; font-size: 0.82rem; color: #1e4b76; cursor: pointer; }
  .cat-tab-active { background: #d4e9ff; border-color: #a9c9ea; font-weight: 700; }
  .cat-dot { display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #3c79c5; margin-left: 4px; vertical-align: middle; }
  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.3rem; }
  .chip { background: #ecf2fb; border: 1px solid #ccddf4; color: #1f4066; border-radius: 999px; padding: 0.3rem 0.75rem; font-size: 0.84rem; cursor: pointer; transition: all 0.1s; }
  .chip-selected { background: #3c79c5; border-color: #3168ad; color: #fff; }
</style>
