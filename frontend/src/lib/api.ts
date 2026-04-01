import Cookies from "js-cookie";
import type {
  Company, CampaignStats, StorySearchResult, MemoryFile, MemoryUpdate, Interview
} from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function getToken(): string {
  return Cookies.get("futuro_token") ?? "";
}

function handleUnauthorized(detail?: string): never {
  Cookies.remove("futuro_token");
  if (typeof window !== "undefined") {
    const message = detail ? `?reason=${encodeURIComponent(detail)}` : "";
    window.location.href = `/login${message}`;
  }
  throw new Error(detail ?? "Session expired. Please sign in again.");
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${getToken()}`,
    ...extra,
  };
}

export async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { ...headers(), ...(init?.headers ?? {}) },
    });
  } catch {
    throw new Error(`Could not reach Futuro backend at ${BASE}. Make sure the local API server is running.`);
  }
  if (res.status === 401) {
    const err = await res.json().catch(() => ({ detail: "Session expired. Please sign in again." }));
    return handleUnauthorized(err.detail);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  if (res.status === 204) {
    return undefined as T;
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(password: string): Promise<{ access_token: string }> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
  } catch {
    throw new Error(`Could not reach Futuro backend at ${BASE}. Make sure the local API server is running.`);
  }
  if (!res.ok) throw new Error("Invalid password");
  const data = await res.json();
  Cookies.set("futuro_token", data.access_token, { expires: 7, sameSite: "strict" });
  return data;
}

export function logout() {
  Cookies.remove("futuro_token");
}

export function isLoggedIn(): boolean {
  return !!Cookies.get("futuro_token");
}

// ── Chat (SSE) ────────────────────────────────────────────────────────────────

export interface ChatMessage { role: "user" | "assistant"; content: string; }

export interface ChatCallbacks {
  onIntent?: (intent: string) => void;
  onToken: (token: string) => void;
  onComplete?: (updates: MemoryUpdate[]) => void;
  onError?: (err: Error) => void;
}

export async function streamChat(
  message: string,
  history: ChatMessage[],
  callbacks: ChatCallbacks,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers: headers({ Accept: "text/event-stream" }),
      body: JSON.stringify({ message, history }),
    });
  } catch {
    callbacks.onError?.(new Error(`Could not reach Futuro backend at ${BASE}. Make sure the local API server is running.`));
    return;
  }

  if (res.status === 401) {
    const err = await res.json().catch(() => ({ detail: "Session expired. Please sign in again." }));
    callbacks.onError?.(new Error(err.detail ?? "Session expired. Please sign in again."));
    handleUnauthorized(err.detail);
  }

  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    callbacks.onError?.(new Error(err.detail ?? "Chat request failed"));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.intent) callbacks.onIntent?.(data.intent);
        if (data.text) callbacks.onToken(data.text);
        if (data.proposed_updates !== undefined) {
          callbacks.onComplete?.(data.proposed_updates ?? []);
        }
      } catch {
        // Partial JSON or non-data line — skip
      }
    }
  }
}

// ── Memory ────────────────────────────────────────────────────────────────────

export const memory = {
  list: () => req<{ files: MemoryFile[] }>("/api/memory/files"),
  get: (filename: string) =>
    req<{ filename: string; content: string; last_modified: string | null; last_commit: string | null }>(
      `/api/memory/${filename}`
    ),
  write: (filename: string, content: string) =>
    req(`/api/memory/${filename}`, { method: "PUT", body: JSON.stringify({ content }) }),
  applyUpdate: (filename: string, update: Omit<MemoryUpdate, "file">) =>
    req(`/api/memory/${filename}/apply-update`, { method: "POST", body: JSON.stringify(update) }),
  gitLog: () => req<{ commits: Array<{ hash: string; message: string; timestamp: string; files_changed: string[] }> }>("/api/memory/git/log"),
};

// ── Campaign ──────────────────────────────────────────────────────────────────

export const campaign = {
  list: (stage?: string) =>
    req<Company[]>(`/api/campaign/companies${stage ? `?stage=${stage}` : ""}`),
  create: (data: { name: string; role_title: string; url?: string; priority?: string; notes?: string; job_description_text?: string }) =>
    req<Company>("/api/campaign/companies", { method: "POST", body: JSON.stringify(data) }),
  updateStage: (id: number, stage: string, description?: string) =>
    req<Company>(`/api/campaign/companies/${id}/stage`, {
      method: "PATCH",
      body: JSON.stringify({ stage, description }),
    }),
  update: (id: number, data: Partial<Company>) =>
    req<Company>(`/api/campaign/companies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  delete: (id: number) =>
    req(`/api/campaign/companies/${id}`, { method: "DELETE" }),
  stats: () => req<CampaignStats>("/api/campaign/stats"),
};

// ── Stories ───────────────────────────────────────────────────────────────────

export const stories = {
  search: (query: string, n_results = 3) =>
    req<{ results: StorySearchResult[] }>("/api/stories/search", {
      method: "POST",
      body: JSON.stringify({ query, n_results }),
    }),
  raw: () => req<{ content: string }>("/api/stories/raw"),
  rebuildIndex: () => req<{ stories_indexed: number; duration_ms: number }>("/api/stories/rebuild-index", { method: "POST" }),
};

// ── Interviews ───────────────────────────────────────────────────────────────

export const interviews = {
  list: () => req<Interview[]>("/api/interviews"),
  create: (data: {
    company_id: number;
    round_name: string;
    format?: string;
    interviewer?: string;
    scheduled_at?: string | null;
  }) =>
    req<Interview>("/api/interviews", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// ── Intake ────────────────────────────────────────────────────────────────────

export async function intakeUrl(url: string, callbacks: ChatCallbacks): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/api/intake/url`, {
      method: "POST",
      headers: headers({ Accept: "text/event-stream" }),
      body: JSON.stringify({ url }),
    });
  } catch {
    callbacks.onError?.(new Error(`Could not reach Futuro backend at ${BASE}. Make sure the local API server is running.`));
    return;
  }
  if (res.status === 401) {
    const err = await res.json().catch(() => ({ detail: "Session expired. Please sign in again." }));
    callbacks.onError?.(new Error(err.detail ?? "Session expired. Please sign in again."));
    handleUnauthorized(err.detail);
  }
  if (!res.ok || !res.body) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    callbacks.onError?.(new Error(err.detail ?? "Intake failed"));
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const data = JSON.parse(line.slice(6));
        if (data.text) callbacks.onToken(data.text);
        if (data.source !== undefined) callbacks.onComplete?.([]);
      } catch { /* skip */ }
    }
  }
}
