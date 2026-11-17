// Loads the newest version of the app: asks the service worker to update, then reloads.
// Only ever called from a click, so it never interrupts someone mid-entry.
export async function refreshToLatest(): Promise<void> {
  // Offline / server restarting: do nothing, so the caches (including the offline page) stay intact.
  try {
    const res = await fetch('/_app/version.json', { cache: 'no-store' });
    if (!res.ok) return;
  } catch {
    return;
  }

  try {
    if ('serviceWorker' in navigator) {
      const registration = await navigator.serviceWorker.getRegistration();
      await registration?.update();
    }
  } catch {
    // A failed service worker update must not block the reload.
  }

  // Deliberately NOT clearing CacheStorage: the service worker only keeps the offline page there and
  // only re-fills it when sw.js itself changes, so wiping it would break the offline screen. The app's
  // own files have build-stamped names, so a reload already fetches the new ones.
  location.reload();
}
