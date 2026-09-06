const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(res.status, error.detail || `API error: ${res.status}`);
  }
  return res.json();
}
