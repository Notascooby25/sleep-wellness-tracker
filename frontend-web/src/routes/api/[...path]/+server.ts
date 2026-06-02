import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

export const trailingSlash = 'ignore';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');
const SLASH_BASE_PATHS = new Set(['categories', 'activities', 'mood']);

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

    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers: outgoingHeaders,
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.arrayBuffer()
    });

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
