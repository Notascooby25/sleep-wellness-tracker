const GET_CACHE_TTL_MS = 15000;
const TIMEOUT_MS = 12000;

type CacheEntry = {
  expiresAt: number;
  data: unknown;
};

const getCache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<unknown>>();

function withTimeout(signal?: AbortSignal | null): AbortSignal {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  controller.signal.addEventListener('abort', () => clearTimeout(timeout), { once: true });
  return controller.signal;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase();
  const cacheKey = `${method}:${path}`;

  if (method === 'GET') {
    const cached = getCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      return cached.data as T;
    }

    const existing = inflight.get(cacheKey);
    if (existing) {
      return (await existing) as T;
    }
  }

  const requestPromise = (async () => {
    const response = await fetch(`/api${path}`, {
      ...init,
      signal: withTimeout(init?.signal),
      headers: {
        'content-type': 'application/json',
        ...(init?.headers || {})
      }
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`${response.status} ${text || response.statusText}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const data = (await response.json()) as T;
    if (method === 'GET') {
      getCache.set(cacheKey, {
        data,
        expiresAt: Date.now() + GET_CACHE_TTL_MS
      });
    }
    return data;
  })();

  if (method === 'GET') {
    inflight.set(cacheKey, requestPromise as Promise<unknown>);
    try {
      return (await requestPromise) as T;
    } finally {
      inflight.delete(cacheKey);
    }
  }

  // For writes, clear cached GET results to avoid stale reads.
  for (const key of getCache.keys()) {
    if (key.startsWith('GET:')) {
      getCache.delete(key);
    }
  }
  return requestPromise;
}

export const getJson = <T>(path: string) => api<T>(path, { method: 'GET' });

export const postJson = <T>(path: string, payload: unknown) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(payload) });

export const putJson = <T>(path: string, payload: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(payload) });

export const deleteJson = <T>(path: string) => api<T>(path, { method: 'DELETE' });
