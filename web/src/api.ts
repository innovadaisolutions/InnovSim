export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    if (payload && typeof payload === 'object') {
      const detail = 'detail' in payload ? payload.detail : 'error' in payload ? payload.error : payload;
      message = typeof detail === 'string' ? detail : JSON.stringify(detail, null, 2);
    }
    throw new Error(message);
  }
  return payload as T;
}
