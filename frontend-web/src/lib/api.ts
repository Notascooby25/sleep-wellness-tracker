export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
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

  return (await response.json()) as T;
}

export const getJson = <T>(path: string) => api<T>(path, { method: 'GET' });

export const postJson = <T>(path: string, payload: unknown) =>
  api<T>(path, { method: 'POST', body: JSON.stringify(payload) });

export const putJson = <T>(path: string, payload: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(payload) });

export const deleteJson = <T>(path: string) => api<T>(path, { method: 'DELETE' });
