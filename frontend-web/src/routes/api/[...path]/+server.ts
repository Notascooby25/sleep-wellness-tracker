import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const trailingSlash = 'ignore';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');
const fallbackBackends = (env.API_BASE_FALLBACKS || '')
  .split(',')
  .map((base) => base.trim())
  .filter(Boolean);
const BACKENDS = Array.from(
  new Set([BACKEND, ...fallbackBackends].map((base) => base.replace(/\/$/, '')))
);
const SLASH_BASE_PATHS = new Set(['categories', 'activities', 'mood', 'categories/position-options']);
const UPLOAD_PATH = 'mood/upload-image';

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const DEFAULT_UPLOAD_FILENAME = 'upload.jpg';

const normalizeUploadFilename = (rawName: string | null) => {
  if (!rawName) return DEFAULT_UPLOAD_FILENAME;
  try {
    const decoded = decodeURIComponent(rawName).trim();
    if (!decoded || decoded.length > 120 || decoded.includes('..') || decoded.startsWith('.')) {
      return DEFAULT_UPLOAD_FILENAME;
    }
    return /^[A-Za-z0-9._-]+$/.test(decoded) ? decoded : DEFAULT_UPLOAD_FILENAME;
  } catch {
    return DEFAULT_UPLOAD_FILENAME;
  }
};

const fetchWithRetry = async (
  targetUrl: string,
  init: RequestInit,
  fetchFn: typeof fetch,
  retries = 2
) => {
  let lastError: unknown = null;
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      return await fetchFn(targetUrl, init);
    } catch (error) {
      lastError = error;
      if (attempt < retries) {
        await sleep(300);
      }
    }
  }
  throw lastError ?? new Error(`Unable to reach backend at ${targetUrl}`);
};

const proxy: RequestHandler = async ({ request, url, fetch }) => {
  // Strip any trailing slash from the path before checking SLASH_BASE_PATHS,
  // so requests like /api/categories/ are normalised to 'categories' for the set lookup.
  let targetPath = url.pathname.replace(/^\/api\/?/, '').replace(/\/$/, '');

  // FastAPI routes with base-only path are defined with trailing slash.
  if (SLASH_BASE_PATHS.has(targetPath)) {
    targetPath = `${targetPath}/`;
  }

  try {
    const incomingContentType = request.headers.get('content-type');
    const outgoingHeaders: Record<string, string> = {};
    if (incomingContentType) {
      outgoingHeaders['content-type'] = incomingContentType;
    }

    const uploadFilename = normalizeUploadFilename(request.headers.get('x-upload-filename'));

    const isUpload =
      targetPath === UPLOAD_PATH &&
      request.method === 'POST' &&
      incomingContentType &&
      !incomingContentType.toLowerCase().startsWith('multipart/form-data');

    const isMultipart =
      incomingContentType?.toLowerCase().startsWith('multipart/form-data') ?? false;

    let requestBody: BodyInit | undefined;
    if (!['GET', 'HEAD'].includes(request.method)) {
      if (isUpload) {
        // Binary upload sent as raw content-type (e.g. image/jpeg) — wrap in FormData
        const rawBody = await request.arrayBuffer();
        const formData = new FormData();
        formData.append('file', new Blob([rawBody], { type: incomingContentType! }), uploadFilename);
        requestBody = formData;
        delete outgoingHeaders['content-type'];
      } else if (isMultipart) {
        // Already multipart (e.g. camera upload from browser) — pass through as binary
        requestBody = await request.arrayBuffer();
      } else {
        // Regular JSON or other text body — use text to avoid Node fetch/undici issues
        requestBody = await request.text();
      }
    }

    let upstream: Response | null = null;
    let lastError: unknown = null;
    for (const backend of BACKENDS) {
      const targetUrl = `${backend}/${targetPath}${url.search}`;
      try {
        upstream = await fetchWithRetry(
          targetUrl,
          {
            method: request.method,
            headers: outgoingHeaders,
            body: requestBody
          },
          fetch
        );
      } catch (error) {
        lastError = error;
      }
      if (upstream) break;
    }

    if (!upstream) {
      throw lastError ?? new Error('Unable to reach backend');
    }

    const body = await upstream.arrayBuffer();
    const responseHeaders = new Headers();
    const upstreamContentType = upstream.headers.get('content-type');
    if (upstreamContentType) {
      responseHeaders.set('content-type', upstreamContentType);
    }
    return new Response(body, {
      status: upstream.status,
      headers: responseHeaders
    });
  } catch (error) {
    return new Response(
      JSON.stringify({ message: 'Upstream backend unavailable', detail: String(error) }),
      {
        status: 502,
        headers: { 'content-type': 'application/json' }
      }
    );
  }
};

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
