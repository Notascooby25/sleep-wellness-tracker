<script lang="ts">
  import { describeError } from '$lib/errors.js';
  import { api, deleteJson, putJson } from '$lib/api';
  import type { HeadacheCheckDay, HeadacheOnset } from '$lib/types';

  /** The day being answered for (YYYY-MM-DD), taken from the entry form's date. */
  export let date: string;
  /** Bump this after saving an entry so items just logged are picked up. */
  export let refreshKey = 0;

  const ONSETS: { value: HeadacheOnset; label: string }[] = [
    { value: 'woke', label: 'Woke with it' },
    { value: 'morning', label: 'Morning' },
    { value: 'afternoon', label: 'Afternoon' },
    { value: 'evening', label: 'Evening' }
  ];

  let check: HeadacheCheckDay | null = null;
  let saving = false;
  let error = '';
  let loadedFor = '';

  const todayKey = () => {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  };

  const dayWords = (iso: string) => {
    if (iso === todayKey()) return 'today';
    const d = new Date(`${iso}T12:00:00`);
    if (Number.isNaN(d.getTime())) return iso;
    return `on ${d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })}`;
  };

  const load = async (day: string) => {
    if (!day) return;
    error = '';
    try {
      // Skip the short-lived GET cache so a just-saved entry shows straight away.
      const result = await api<HeadacheCheckDay>(`/headache-checks/${day}?fresh=${Date.now()}`);
      if (day === date) check = result;
    } catch (err) {
      error = `Couldn't load the headache check: ${describeError(err)}`;
    }
  };

  $: if (date && `${date}:${refreshKey}` !== loadedFor) {
    loadedFor = `${date}:${refreshKey}`;
    check = null;
    load(date);
  }

  const save = async (hadHeadache: boolean, onset: HeadacheOnset | null = null) => {
    if (saving) return;
    saving = true;
    error = '';
    try {
      check = await putJson<HeadacheCheckDay>(`/headache-checks/${date}`, { had_headache: hadHeadache, onset });
    } catch (err) {
      error = `Couldn't save: ${describeError(err)}`;
    } finally {
      saving = false;
    }
  };

  const chooseYes = () => save(true, check?.had_headache ? check.onset : null);
  const chooseOnset = (onset: HeadacheOnset) => save(true, check?.onset === onset ? null : onset);

  const undo = async () => {
    if (saving) return;
    saving = true;
    error = '';
    try {
      check = await deleteJson<HeadacheCheckDay>(`/headache-checks/${date}`);
    } catch (err) {
      error = `Couldn't clear: ${describeError(err)}`;
    } finally {
      saving = false;
    }
  };

  $: answeredYes = check?.answered === true && check.had_headache === true;
  $: answeredNo = check?.answered === true && check.had_headache === false;
  // Before answering, a headache item already logged that day suggests "Yes".
  $: suggestYes = check !== null && !check.answered && check.logged_symptoms.length > 0;
</script>

<section class="card headache-check" aria-labelledby="headache-check-title">
  <div class="hc-head">
    <h2 id="headache-check-title">Headache {dayWords(date)}?</h2>
    {#if check?.answered}
      <span class="hc-saved" role="status">Saved</span>
    {/if}
  </div>
  <p class="hc-hint">
    One tap a day. It tells the headache report which days were truly clear, so it can find causes more accurately.
  </p>

  <div class="hc-choices" role="group" aria-label="Did you have a headache?">
    <button
      type="button"
      class="hc-btn"
      class:hc-selected={answeredNo}
      aria-pressed={answeredNo}
      disabled={saving || check === null}
      on:click={() => save(false)}
    >No</button>
    <button
      type="button"
      class="hc-btn"
      class:hc-selected={answeredYes}
      class:hc-suggested={suggestYes}
      aria-pressed={answeredYes}
      disabled={saving || check === null}
      on:click={chooseYes}
    >Yes</button>
  </div>

  {#if suggestYes}
    <p class="hc-note">You logged {check?.logged_symptoms.join(', ')} {dayWords(date)}. Tap Yes or No to confirm.</p>
  {/if}

  {#if answeredYes}
    <div class="hc-onset">
      <div class="hc-label">When did it start?</div>
      <div class="hc-choices" role="group" aria-label="When did the headache start?">
        {#each ONSETS as option}
          <button
            type="button"
            class="hc-btn hc-small"
            class:hc-selected={check?.onset === option.value}
            aria-pressed={check?.onset === option.value}
            disabled={saving}
            on:click={() => chooseOnset(option.value)}
          >{option.label}</button>
        {/each}
      </div>
    </div>
  {/if}

  {#if check?.answered}
    <button type="button" class="hc-undo" disabled={saving} on:click={undo}>Clear answer</button>
  {/if}

  {#if error}
    <p class="hc-error" role="alert">{error}</p>
  {/if}
</section>

<style>
  .headache-check h2 { margin: 0; font-size: 1.1rem; color: var(--color-primary-content); }
  .hc-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
  .hc-saved { font-size: 0.78rem; font-weight: 700; color: var(--color-success-text); background: var(--color-success-bg); border-radius: 999px; padding: 0.15rem 0.55rem; }
  .hc-hint { margin: 0.3rem 0 0.6rem; font-size: 0.86rem; color: var(--color-neutral-text-muted); }
  .hc-choices { display: flex; flex-wrap: wrap; gap: 0.5rem; }
  .hc-btn {
    flex: 1 1 0;
    min-width: 5.5rem;
    min-height: 44px;
    border-radius: 999px;
    border: 1px solid var(--color-input-border);
    background: var(--color-surface-subtle);
    color: var(--color-primary-content);
    font-size: 1rem;
    font-weight: 700;
    cursor: pointer;
  }
  .hc-small { font-size: 0.88rem; font-weight: 600; }
  .hc-selected { background: var(--color-accent); border-color: var(--color-accent-border); color: var(--color-neutral-bg); }
  .hc-suggested:not(.hc-selected) { border-color: var(--color-accent); border-width: 2px; }
  .hc-btn:disabled { opacity: 0.6; cursor: default; }
  .hc-note { margin: 0.5rem 0 0; font-size: 0.84rem; color: var(--color-neutral-text-muted); }
  .hc-onset { margin-top: 0.75rem; }
  .hc-onset .hc-choices { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hc-label { font-size: 0.9rem; font-weight: 600; color: var(--color-neutral-text); margin-bottom: 0.35rem; }
  .hc-undo {
    margin-top: 0.6rem;
    min-height: 44px;
    background: transparent;
    border: none;
    padding: 0 0.25rem;
    color: var(--color-link);
    font-size: 0.84rem;
    text-decoration: underline;
    cursor: pointer;
  }
  .hc-error { margin: 0.5rem 0 0; font-size: 0.86rem; color: var(--color-error); background: var(--color-error-bg); border-radius: 8px; padding: 0.3rem 0.6rem; }
</style>
