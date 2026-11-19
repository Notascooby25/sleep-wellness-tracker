import type { Handle } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');

// Paths that must stay reachable without a session (login page, its API calls, static/PWA assets).
const PUBLIC_PREFIXES = [
  '/login',
  '/api/auth/',
  '/_app/',
  '/favicon',
  '/manifest.webmanifest',
  '/sw.js',
  '/offline.html',
  '/icons/'
];

const isPublicPath = (pathname: string) => PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));

const withSecurityHeaders = (response: Response): Response => {
  response.headers.set('X-Content-Type-Options', 'nosniff');
  response.headers.set('X-Frame-Options', 'DENY');
  response.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
  response.headers.set('Permissions-Policy', 'camera=(), microphone=()');
  return response;
};

export const handle: Handle = async ({ event, resolve }) => {
  if (isPublicPath(event.url.pathname)) {
    return withSecurityHeaders(await resolve(event));
  }

  const cookie = event.request.headers.get('cookie') ?? '';
  try {
    const statusResponse = await fetch(`${BACKEND}/auth/status`, {
      headers: cookie ? { cookie } : {}
    });
    const status = await statusResponse.json();
    if (status.auth_required && !status.authenticated) {
      const redirectTo = encodeURIComponent(event.url.pathname + event.url.search);
      return withSecurityHeaders(
        new Response(null, {
          status: 303,
          headers: { location: `/login?redirect=${redirectTo}` }
        })
      );
    }
  } catch {
    // Backend unreachable — let the request through; API calls will fail visibly instead.
  }

  return withSecurityHeaders(await resolve(event));
};
