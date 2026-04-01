/**
 * Internal fetch helper used by components that can't import from api.ts
 * (avoids circular dependency via store.ts).
 */
export async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}
