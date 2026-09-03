import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');

// Paths that must stay reachable without a session (login page, its API calls, static assets).
const PUBLIC_PREFIXES = ['/login', '/api/auth/', '/_app/', '/favicon', '/manifest.webmanifest'];

const isPublicPath = (pathname: string) => PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));

export const handle: Handle = async ({ event, resolve }) => {
  if (isPublicPath(event.url.pathname)) {
    return resolve(event);
  }

  const cookie = event.request.headers.get('cookie') ?? '';
  try {
    const statusResponse = await fetch(`${BACKEND}/auth/status`, {
      headers: cookie ? { cookie } : {}
    });
    const status = await statusResponse.json();
    if (status.auth_required && !status.authenticated) {
      const redirectTo = encodeURIComponent(event.url.pathname + event.url.search);
      return new Response(null, {
        status: 303,
        headers: { location: `/login?redirect=${redirectTo}` }
      });
    }
  } catch {
    // Backend unreachable — let the request through; API calls will fail visibly instead.
  }

  return resolve(event);
};
