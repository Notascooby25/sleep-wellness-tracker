import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const trailingSlash = 'ignore';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');
const SLASH_BASE_PATHS = new Set(['categories', 'activities', 'mood']);

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const proxy: RequestHandler = async ({ request, url, fetch }) => {
  // Strip any trailing slash from the path before checking SLASH_BASE_PATHS,
  // so requests like /api/categories/ are normalised to 'categories' for the set lookup.
  let targetPath = url.pathname.replace(/^\/api\/?/, '').replace(/\/$/, '');

  // FastAPI routes with base-only path are defined with trailing slash.
  if (SLASH_BASE_PATHS.has(targetPath)) {
    targetPath = `${targetPath}/`;
  }

  const targetUrl = `${BACKEND}/${targetPath}${url.search}`;
  try {
    const incomingContentType = request.headers.get('content-type');
    const outgoingHeaders: Record<string, string> = {};
    if (incomingContentType) {
      outgoingHeaders['content-type'] = incomingContentType;
    }

    const requestBody = ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer();

    let upstream: Response | null = null;
    let lastError: unknown = null;
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        upstream = await fetch(targetUrl, {
          method: request.method,
          headers: outgoingHeaders,
          body: requestBody
        });
        break;
      } catch (error) {
        lastError = error;
        if (attempt < 2) {
          await sleep(300);
          continue;
        }
      }
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
