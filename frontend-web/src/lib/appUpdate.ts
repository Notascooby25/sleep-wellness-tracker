// Loads the newest version of the app: asks the service worker to update, clears old caches, reloads.
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

  try {
    if ('caches' in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
    }
  } catch {
    // Same: reload anyway.
  }

  location.reload();
}
