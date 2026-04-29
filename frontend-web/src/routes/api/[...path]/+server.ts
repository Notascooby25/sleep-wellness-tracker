import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const BACKEND = (env.API_BASE || 'http://backend:8000').replace(/\/$/, '');

const proxy: RequestHandler = async ({ params, request, url, fetch }) => {
  const targetPath = params.path || '';
  const targetUrl = `${BACKEND}/${targetPath}${url.search}`;
  try {
    const upstream = await fetch(targetUrl, {
      method: request.method,
      headers: {
        'content-type': request.headers.get('content-type') || 'application/json'
      },
      body: ['GET', 'HEAD'].includes(request.method) ? undefined : await request.text()
    });

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        'content-type': upstream.headers.get('content-type') || 'application/json'
      }
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
