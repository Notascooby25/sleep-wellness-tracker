import { goto } from '$app/navigation';
import { ApiError } from './errors.js';

// If the session has ended, send the person to the login page and bring them back afterwards.
// Several requests can fail together, so only the first one redirects.
let signedOutHandled = false;
function handleSignedOut() {
  if (typeof window === 'undefined' || signedOutHandled) return;
  if (window.location.pathname.startsWith('/login')) return;
  signedOutHandled = true;
  const here = window.location.pathname + window.location.search;
  void goto(`/login?redirect=${encodeURIComponent(here)}`);
  setTimeout(() => (signedOutHandled = false), 3000);
}

const GET_CACHE_TTL_MS = 15000;
const TIMEOUT_MS = 12000;

type CacheEntry = {
  expiresAt: number;
  data: unknown;
};

const getCache = new Map<string, CacheEntry>();
const inflight = new Map<string, Promise<unknown>>();

function withTimeout(signal?: AbortSignal | null): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const clear = () => clearTimeout(timeout);

  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener('abort', () => controller.abort(), { once: true });
    }
  }

  // clearTimeout is idempotent; registering it on both the abort event and the
  // finally block ensures the timer is cancelled on both early abort and normal completion.
  controller.signal.addEventListener('abort', clear, { once: true });
  return { signal: controller.signal, clear };
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
    const { signal, clear } = withTimeout(init?.signal);
    try {
      const response = await fetch(`/api${path}`, {
        ...init,
        signal,
        headers: {
          'content-type': 'application/json',
          ...(init?.headers || {})
        }
      });

      if (!response.ok) {
        const text = await response.text();
        let detail: unknown = text || response.statusText;
        try {
          const parsed = JSON.parse(text);
          if (parsed && typeof parsed === 'object' && 'detail' in parsed) detail = parsed.detail;
        } catch {
          // not JSON: keep the text
        }
        // Raw details stay in the browser console for debugging; people see describeError() text.
        console.warn(`API ${method} ${path} failed with ${response.status}:`, text.slice(0, 300));
        if (response.status === 401 && !path.startsWith('/auth/')) handleSignedOut();
        throw new ApiError(response.status, detail, text || response.statusText);
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
    } finally {
      clear();
    }
  })();

  if (method === 'GET') {
    inflight.set(cacheKey, requestPromise as Promise<unknown>);
    try {
      return (await requestPromise) as T;
    } finally {
      inflight.delete(cacheKey);
    }
  }

  // For writes, invalidate only GET cache entries for the same resource group.
  // activities and categories are treated as one group since they are related;
  // an item's report role also changes the impact and report results.
  const firstSegment = path.split('/').filter(Boolean)[0] || '';
  const invalidatePrefixes =
    firstSegment === 'activities' || firstSegment === 'categories'
      ? ['GET:/activities', 'GET:/categories', 'GET:/lifestyle-impact', 'GET:/reports']
      : [`GET:/${firstSegment}`];

  for (const key of getCache.keys()) {
    if (invalidatePrefixes.some((p) => key.startsWith(p))) {
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
