"use client";

import { useEffect, useState } from "react";
import { Cpu, Cloud, Download, RefreshCw, CheckCircle, AlertCircle, X } from "lucide-react";
import clsx from "clsx";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const m = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return m ? m[2] : "";
}

async function apiFetch(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: { Authorization: `Bearer ${getCookie("futuro_token")}`, "Content-Type": "application/json", ...(opts.headers ?? {}) },
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `${res.status}`);
  }
  return res.json();
}

interface ProviderHealth {
  ok: boolean;
  model: string;
  detail: string;
  embed_model?: string;
  available_models?: string[];
}

type GlobalProviderValue = "auto" | "ollama" | "claude";
type ProviderOverrideValue = "" | "ollama" | "claude";
type TaskProviderField = "chat_provider" | "classify_provider" | "score_provider" | "embed_provider";

interface ProviderStatusResponse {
  routing: Record<string, { provider: string; model: string }>;
  config: {
    llm_provider: GlobalProviderValue;
    chat_provider: "ollama" | "claude" | null;
    classify_provider: "ollama" | "claude" | null;
    score_provider: "ollama" | "claude" | null;
    embed_provider: "ollama" | "claude" | null;
  };
  ollama: {
    enabled: boolean;
    base_url: string;
    chat_model: string;
    embed_model: string;
  };
}

interface OllamaModel {
  name: string;
  size: number;
  modified_at: string;
}

interface PullEvent {
  status?: string;
  completed?: number;
  total?: number;
  digest?: string;
  error?: string;
  model?: string;
}

interface ProviderConfigForm {
  llm_provider: GlobalProviderValue;
  chat_provider: ProviderOverrideValue;
  classify_provider: ProviderOverrideValue;
  score_provider: ProviderOverrideValue;
  embed_provider: ProviderOverrideValue;
  ollama_enabled: boolean;
  ollama_chat_model: string;
  ollama_embed_model: string;
}

const QWEN_MODELS = [
  { id: "qwen2.5:7b",    label: "Qwen 2.5 7B",  ram: "4 GB",  note: "Fast, daily use"        },
  { id: "qwen2.5:14b",   label: "Qwen 2.5 14B", ram: "9 GB",  note: "Balanced quality/speed" },
  { id: "qwen2.5:32b",   label: "Qwen 2.5 32B", ram: "20 GB", note: "Near-Claude quality"    },
  { id: "qwen2.5:72b",   label: "Qwen 2.5 72B", ram: "45 GB", note: "Maximum quality"        },
];

const EMBED_MODELS = [
  { id: "nomic-embed-text",  label: "nomic-embed-text",  size: "270 MB", note: "Recommended — fast, high quality" },
  { id: "mxbai-embed-large", label: "mxbai-embed-large", size: "670 MB", note: "Stronger retrieval"               },
  { id: "qwen2.5:7b",       label: "qwen2.5:7b (dual)", size: "4 GB",   note: "Reuse chat model, no extra pull"  },
];

function fmtBytes(b: number) {
  if (b > 1e9) return `${(b / 1e9).toFixed(1)} GB`;
  if (b > 1e6) return `${(b / 1e6).toFixed(0)} MB`;
  return `${b} B`;
}

// ── Pull progress modal ───────────────────────────────────────────────────────

function PullModal({ model, onDone, onClose }: { model: string; onDone: () => void; onClose: () => void }) {
  const [lines, setLines] = useState<string[]>([]);
  const [done,  setDone]  = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState("Preparing download…");
  const [completed, setCompleted] = useState<number | null>(null);
  const [total, setTotal] = useState<number | null>(null);

  const percent = total && total > 0 && completed !== null
    ? Math.max(0, Math.min(100, Math.round((completed / total) * 100)))
    : null;

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function pull() {
      try {
        const res = await fetch(`${API}/api/providers/pull`, {
          method: "POST",
          headers: { Authorization: `Bearer ${getCookie("futuro_token")}`, "Content-Type": "application/json" },
          body: JSON.stringify({ model }),
          signal: controller.signal,
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          const msg = detail?.detail ? `Pull failed (${res.status}): ${detail.detail}` : `Pull failed (${res.status})`;
          throw new Error(msg);
        }
        if (!res.body) throw new Error("No download stream returned");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (!cancelled) {
          const { done: d, value } = await reader.read();
          if (d) break;
          buf += decoder.decode(value, { stream: true });
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            try {
              const data = JSON.parse(line.slice(6)) as PullEvent;
              if (data.status === "success") {
                setDone(true);
                setStatusText("Download complete");
                onDone();
                return;
              }
              if (data.status === "error") {
                setError(data.error ?? "Unknown pull error");
                setStatusText("Download failed");
                return;
              }

              if (typeof data.completed === "number") setCompleted(data.completed);
              if (typeof data.total === "number") setTotal(data.total);

              const digest = data.digest ? ` · ${data.digest.slice(7, 19)}` : "";
              const msg = data.status ?? "Working";
              const nextStatus = `${msg}${digest}`;
              setStatusText(nextStatus);

              const pct = data.total && typeof data.completed === "number"
                ? Math.round((data.completed / data.total) * 100)
                : null;
              const display = pct !== null ? `${nextStatus} · ${pct}%` : nextStatus;
              if (display) setLines(l => [...l.slice(-8), display]);
            } catch { /* skip */ }
          }
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e.message);
          setStatusText("Download failed");
        }
      }
    }
    pull();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [model]);

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-900 text-sm">Pulling {model}</h2>
          {(done || error) && <button onClick={onClose}><X size={16} className="text-gray-400" /></button>}
        </div>
        <div className="px-6 py-4 bg-gray-50 rounded-b-none space-y-4">
          <div>
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="text-gray-600 truncate">{statusText}</span>
              <span className="font-mono text-gray-500 flex-shrink-0">
                {done ? "100%" : percent !== null ? `${percent}%` : "…"}
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-gray-200 overflow-hidden">
              {percent !== null || done ? (
                <div
                  className={clsx(
                    "h-full rounded-full transition-all duration-300",
                    done ? "bg-green-500" : "bg-futuro-500"
                  )}
                  style={{ width: `${done ? 100 : percent}%` }}
                />
              ) : (
                <div className="h-full w-1/3 rounded-full bg-futuro-400 animate-pulse" />
              )}
            </div>
            {(completed !== null && total !== null) && (
              <div className="mt-1 text-[11px] text-gray-400 font-mono">
                {fmtBytes(completed)} / {fmtBytes(total)}
              </div>
            )}
          </div>

          <div className="font-mono text-xs text-gray-600 min-h-[80px] space-y-1">
            {lines.map((l, i) => <div key={i}>{l}</div>)}
            {!done && !error && lines.length === 0 && (
              <div className="text-gray-400 animate-pulse">Downloading…</div>
            )}
          </div>
        </div>
        <div className="px-6 py-3 border-t flex items-center gap-2">
          {done  && <><CheckCircle size={14} className="text-green-500" /><span className="text-sm text-green-600">Done! Restart Futuro to activate.</span></>}
          {error && <><AlertCircle size={14} className="text-red-400" /><span className="text-sm text-red-600">{error}</span></>}
          {!done && !error && <span className="text-xs text-gray-400">This may take several minutes…</span>}
        </div>
      </div>
    </div>
  );
}

// ── Main settings page ────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [health,     setHealth]     = useState<Record<string, ProviderHealth>>({});
  const [routing,    setRouting]    = useState<Record<string, { provider: string; model: string }>>({});
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [status,     setStatus]     = useState<ProviderStatusResponse | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [pulling,    setPulling]    = useState<string | null>(null);
  const [saving,     setSaving]     = useState(false);
  const [saveError,  setSaveError]  = useState<string | null>(null);
  const [saveNote,   setSaveNote]   = useState<string | null>(null);
  const [form,       setForm]       = useState<ProviderConfigForm>({
    llm_provider: "auto",
    chat_provider: "",
    classify_provider: "",
    score_provider: "",
    embed_provider: "",
    ollama_enabled: true,
    ollama_chat_model: "qwen2.5:7b",
    ollama_embed_model: "nomic-embed-text",
  });

  async function loadAll() {
    setLoading(true);
    try {
      const [h, s, m] = await Promise.all([
        apiFetch("/api/providers/health"),
        apiFetch("/api/providers/status"),
        apiFetch("/api/providers/models"),
      ]);
      setHealth(h);
      setStatus(s);
      setRouting(s.routing ?? {});
      setOllamaModels(m.models ?? []);
    } catch { /* ignore */ }
    setLoading(false);
  }

  useEffect(() => { loadAll(); }, []);

  useEffect(() => {
    if (!status) return;
    setForm({
      llm_provider: status.config?.llm_provider ?? "auto",
      chat_provider: status.config?.chat_provider ?? "",
      classify_provider: status.config?.classify_provider ?? "",
      score_provider: status.config?.score_provider ?? "",
      embed_provider: status.config?.embed_provider ?? "",
      ollama_enabled: status.ollama?.enabled ?? true,
      ollama_chat_model: status.ollama?.chat_model ?? "qwen2.5:7b",
      ollama_embed_model: status.ollama?.embed_model ?? "nomic-embed-text",
    });
  }, [status]);

  const pulledIds = new Set(ollamaModels.map(m => m.name));
  const chatModelOptions = Array.from(new Set([
    ...QWEN_MODELS.map(m => m.id),
    ...ollamaModels.map(m => m.name),
    form.ollama_chat_model,
  ]));
  const embedModelOptions = Array.from(new Set([
    ...EMBED_MODELS.map(m => m.id),
    ...ollamaModels.map(m => m.name),
    form.ollama_embed_model,
  ]));

  const TASK_LABELS: Record<string, string> = {
    chat: "Chat", classify: "Classify", score: "Score", embed: "Embed",
  };

  function setTaskProvider(field: TaskProviderField, value: ProviderOverrideValue) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function applyPreset(mode: "prefer_ollama" | "ollama_only" | "claude_only") {
    setSaveError(null);
    setSaveNote(null);

    if (mode === "prefer_ollama") {
      setForm((current) => ({
        ...current,
        llm_provider: "auto",
        chat_provider: "",
        classify_provider: "",
        score_provider: "",
        embed_provider: "",
        ollama_enabled: true,
      }));
      return;
    }

    if (mode === "ollama_only") {
      setForm((current) => ({
        ...current,
        llm_provider: "ollama",
        chat_provider: "",
        classify_provider: "",
        score_provider: "",
        embed_provider: "",
        ollama_enabled: true,
      }));
      return;
    }

    setForm((current) => ({
      ...current,
      llm_provider: "claude",
      chat_provider: "",
      classify_provider: "",
      score_provider: "",
      embed_provider: "",
      ollama_enabled: current.ollama_enabled,
    }));
  }

  async function saveConfig() {
    setSaving(true);
    setSaveError(null);
    setSaveNote(null);

    try {
      const next = await apiFetch("/api/providers/config", {
        method: "PUT",
        body: JSON.stringify({
          llm_provider: form.llm_provider,
          chat_provider: form.chat_provider || null,
          classify_provider: form.classify_provider || null,
          score_provider: form.score_provider || null,
          embed_provider: form.embed_provider || null,
          ollama_enabled: form.ollama_enabled,
          ollama_chat_model: form.ollama_chat_model,
          ollama_embed_model: form.ollama_embed_model,
        }),
      }) as ProviderStatusResponse & { health?: Record<string, ProviderHealth> };

      setStatus(next);
      setRouting(next.routing ?? {});
      setHealth(next.health ?? {});
      setSaveNote(
        next.config.llm_provider === "auto"
          ? "Applied. Futuro will prefer Ollama whenever it is available."
          : "Applied immediately."
      );
    } catch (e: any) {
      setSaveError(e.message ?? "Failed to save provider settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-thin">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white sticky top-0 z-10">
        <h1 className="font-semibold text-gray-900">Settings</h1>
        <button onClick={loadAll} disabled={loading}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 px-2 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
          <RefreshCw size={12} className={loading ? "animate-spin" : ""} /> Refresh
        </button>
      </div>

      <div className="flex-1 p-6 max-w-3xl space-y-8">

        {/* ── Provider preference ─────────────────────────────────────────── */}
        <section>
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <h2 className="text-sm font-semibold text-gray-700">Provider preference</h2>
              <p className="text-xs text-gray-400 mt-1">
                Choose what Futuro should use. Recommended: <span className="font-medium text-gray-600">Auto (prefer Ollama)</span>.
              </p>
            </div>
            <button
              onClick={saveConfig}
              disabled={saving}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-futuro-500 hover:bg-futuro-600 disabled:opacity-50 text-white rounded-lg transition-colors flex-shrink-0"
            >
              {saving ? <RefreshCw size={12} className="animate-spin" /> : <CheckCircle size={12} />}
              {saving ? "Applying…" : "Apply"}
            </button>
          </div>

          {(saveNote || saveError) && (
            <div className={clsx(
              "mb-4 rounded-xl border px-4 py-3 text-xs",
              saveError ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"
            )}>
              {saveError ?? saveNote}
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
            {[
              {
                id: "prefer_ollama",
                label: "Auto (Prefer Ollama)",
                desc: "Use Ollama first, fall back when needed",
              },
              {
                id: "ollama_only",
                label: "Ollama Only",
                desc: "Stay fully local when possible",
              },
              {
                id: "claude_only",
                label: "Claude Only",
                desc: "Force cloud routing for all tasks",
              },
            ].map((preset) => (
              <button
                key={preset.id}
                onClick={() => applyPreset(preset.id as "prefer_ollama" | "ollama_only" | "claude_only")}
                className="rounded-xl border border-gray-200 bg-white px-3 py-3 text-left hover:border-futuro-300 hover:bg-futuro-50 transition-colors"
              >
                <p className="text-sm font-medium text-gray-800">{preset.label}</p>
                <p className="text-xs text-gray-500 mt-1">{preset.desc}</p>
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <label className="block">
              <span className="text-xs font-medium text-gray-600">Global provider</span>
              <select
                value={form.llm_provider}
                onChange={(e) => setForm((current) => ({ ...current, llm_provider: e.target.value as GlobalProviderValue }))}
                className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-futuro-500"
              >
                <option value="auto">Auto (prefer Ollama)</option>
                <option value="ollama">Ollama only</option>
                <option value="claude">Claude only</option>
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-gray-600">Ollama access</span>
              <select
                value={form.ollama_enabled ? "enabled" : "disabled"}
                onChange={(e) => setForm((current) => ({ ...current, ollama_enabled: e.target.value === "enabled" }))}
                className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-futuro-500"
              >
                <option value="enabled">Enabled</option>
                <option value="disabled">Disabled</option>
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-gray-600">Ollama chat model</span>
              <select
                value={form.ollama_chat_model}
                onChange={(e) => setForm((current) => ({ ...current, ollama_chat_model: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-futuro-500"
              >
                {chatModelOptions.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="text-xs font-medium text-gray-600">Ollama embed model</span>
              <select
                value={form.ollama_embed_model}
                onChange={(e) => setForm((current) => ({ ...current, ollama_embed_model: e.target.value }))}
                className="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-futuro-500"
              >
                {embedModelOptions.map((model) => (
                  <option key={model} value={model}>{model}</option>
                ))}
              </select>
            </label>
          </div>

          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Task</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Override</th>
                </tr>
              </thead>
              <tbody>
                {([
                  ["chat", "Chat", "chat_provider"],
                  ["classify", "Classify", "classify_provider"],
                  ["score", "Score", "score_provider"],
                  ["embed", "Embed", "embed_provider"],
                ] as Array<[string, string, TaskProviderField]>).map(([task, label, field], i) => (
                  <tr key={task} className={clsx("border-b border-gray-100 last:border-0", i % 2 === 0 ? "bg-white" : "bg-gray-50/50")}>
                    <td className="px-4 py-2.5 font-medium text-gray-800">{label}</td>
                    <td className="px-4 py-2.5">
                      <select
                        value={form[field]}
                        onChange={(e) => setTaskProvider(field, e.target.value as ProviderOverrideValue)}
                        className="w-full rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-futuro-500"
                      >
                        <option value="">Follow global</option>
                        <option value="ollama">Prefer Ollama</option>
                        <option value="claude">Use Claude</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── Provider health ───────────────────────────────────────────────── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Provider health</h2>
          <div className="space-y-2">
            {Object.entries(health).length === 0 && loading && (
              <div className="text-sm text-gray-400">Loading…</div>
            )}
            {Object.entries(health).map(([name, h]) => (
              <div key={name} className={clsx(
                "flex items-start gap-3 px-4 py-3 rounded-xl border",
                h.ok ? "bg-green-50 border-green-200" : "bg-red-50 border-red-200"
              )}>
                <span className={clsx("mt-0.5", h.ok ? "text-green-500" : "text-red-400")}>
                  {h.ok ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm capitalize text-gray-900">{name}</span>
                    <span className="text-xs text-gray-500 font-mono">{h.model}</span>
                    {h.embed_model && <span className="text-xs text-gray-400">· embed: {h.embed_model}</span>}
                  </div>
                  <p className="text-xs text-gray-600 mt-0.5">{h.detail}</p>
                  {!h.ok && name === "ollama" && (
                    <p className="text-xs text-amber-700 mt-1 font-mono">
                      $ ollama serve
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ── Task routing ──────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Task routing</h2>
          <p className="text-xs text-gray-400 mb-3">
            Set in <code className="font-mono bg-gray-100 px-1 rounded">.env</code> — change and restart to update.
          </p>
          <div className="border border-gray-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Task</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Provider</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Model</th>
                  <th className="text-left px-4 py-2 text-xs font-medium text-gray-500">Env var</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(routing).map(([task, entry], i) => (
                  <tr key={task} className={clsx("border-b border-gray-100 last:border-0", i % 2 === 0 ? "bg-white" : "bg-gray-50/50")}>
                    <td className="px-4 py-2.5 font-medium text-gray-800">{TASK_LABELS[task] ?? task}</td>
                    <td className="px-4 py-2.5">
                      <span className={clsx(
                        "inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium",
                        entry.provider === "ollama"
                          ? "bg-purple-100 text-purple-700"
                          : "bg-blue-100 text-blue-700"
                      )}>
                        {entry.provider === "ollama" ? <Cpu size={10} /> : <Cloud size={10} />}
                        {entry.provider}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-600">{entry.model}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-gray-400">
                      {task.toUpperCase()}_PROVIDER
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Routing presets */}
          <div className="mt-3 grid grid-cols-3 gap-2">
            {[
              { label: "Full local",  hint: "LLM_PROVIDER=ollama",            desc: "All tasks → Qwen" },
              { label: "Hybrid",      hint: "LLM_PROVIDER=auto",              desc: "Chat local, score cloud" },
              { label: "Full cloud",  hint: "LLM_PROVIDER=claude",            desc: "All tasks → Claude" },
            ].map(p => (
              <div key={p.label} className="border border-gray-200 rounded-xl px-3 py-2.5 bg-gray-50">
                <p className="text-xs font-medium text-gray-700">{p.label}</p>
                <code className="text-xs text-gray-500 font-mono">{p.hint}</code>
                <p className="text-xs text-gray-400 mt-0.5">{p.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Ollama model management ───────────────────────────────────────── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-1">Ollama models</h2>
          <p className="text-xs text-gray-400 mb-4">
            Pull models to your machine. After pulling, update <code className="font-mono bg-gray-100 px-1 rounded">OLLAMA_CHAT_MODEL</code> in <code className="font-mono bg-gray-100 px-1 rounded">.env</code> and restart.
          </p>
          {status?.ollama?.enabled === false && (
            <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-xs text-amber-800">
                Ollama downloads are allowed here even though <code className="font-mono">OLLAMA_ENABLED=false</code> right now.
                After the model finishes downloading, set <code className="font-mono">OLLAMA_ENABLED=true</code> in <code className="font-mono">.env</code> and restart if you want Futuro to use it.
              </p>
            </div>
          )}

          {/* Chat models */}
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Qwen 2.5 — chat models</h3>
          <div className="space-y-2 mb-6">
            {QWEN_MODELS.map(m => {
              const isPulled = pulledIds.has(m.id);
              const isActive = status?.ollama?.chat_model === m.id;
              return (
                <div key={m.id} className={clsx(
                  "flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors",
                  isActive ? "border-futuro-300 bg-futuro-50" : "border-gray-200 bg-white"
                )}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-900">{m.label}</span>
                      {isActive && <span className="text-xs bg-futuro-100 text-futuro-700 px-1.5 py-0.5 rounded">active</span>}
                      {isPulled && !isActive && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">pulled</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{m.note} · requires {m.ram} RAM</p>
                    <code className="text-xs text-gray-400 font-mono">{m.id}</code>
                  </div>
                  {isPulled ? (
                    <CheckCircle size={16} className="text-green-500 flex-shrink-0" />
                  ) : (
                    <button
                      onClick={() => setPulling(m.id)}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-futuro-500 hover:bg-futuro-600 text-white rounded-lg transition-colors flex-shrink-0"
                    >
                      <Download size={12} /> Pull
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Embed models */}
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Embedding models</h3>
          <div className="space-y-2">
            {EMBED_MODELS.map(m => {
              const isPulled = pulledIds.has(m.id) || m.id.startsWith("qwen2.5");
              const isActive = status?.ollama?.embed_model === m.id;
              return (
                <div key={m.id} className={clsx(
                  "flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors",
                  isActive ? "border-teal-300 bg-teal-50" : "border-gray-200 bg-white"
                )}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm text-gray-900">{m.label}</span>
                      {isActive && <span className="text-xs bg-teal-100 text-teal-700 px-1.5 py-0.5 rounded">active</span>}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{m.note} · {m.size}</p>
                    <code className="text-xs text-gray-400 font-mono">{m.id}</code>
                  </div>
                  {isPulled ? (
                    <CheckCircle size={16} className="text-green-500 flex-shrink-0" />
                  ) : (
                    <button
                      onClick={() => setPulling(m.id)}
                      className="flex items-center gap-1.5 text-xs px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                    >
                      <Download size={12} /> Pull
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Pulled models list */}
          {ollamaModels.length > 0 && (
            <div className="mt-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">All pulled models</h3>
              <div className="border border-gray-200 rounded-xl overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="text-left px-3 py-2 text-gray-500 font-medium">Model</th>
                      <th className="text-left px-3 py-2 text-gray-500 font-medium">Size</th>
                      <th className="text-left px-3 py-2 text-gray-500 font-medium">Modified</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ollamaModels.map(m => (
                      <tr key={m.name} className="border-b border-gray-100 last:border-0">
                        <td className="px-3 py-2 font-mono text-gray-700">{m.name}</td>
                        <td className="px-3 py-2 text-gray-500">{fmtBytes(m.size)}</td>
                        <td className="px-3 py-2 text-gray-400">{new Date(m.modified_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        {/* ── Quick setup commands ──────────────────────────────────────────── */}
        <section>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Quick setup</h2>
          <div className="bg-gray-900 rounded-xl p-4 text-xs font-mono text-gray-300 space-y-2 leading-relaxed">
            <div className="text-gray-500"># 1. Install Ollama</div>
            <div>curl -fsSL https://ollama.ai/install.sh | sh</div>
            <div className="text-gray-500 mt-3"># 2. Pull recommended models</div>
            <div>ollama pull qwen2.5:7b</div>
            <div>ollama pull nomic-embed-text</div>
            <div className="text-gray-500 mt-3"># 3. Update .env</div>
            <div>LLM_PROVIDER=auto</div>
            <div>OLLAMA_CHAT_MODEL=qwen2.5:7b</div>
            <div>OLLAMA_EMBED_MODEL=nomic-embed-text</div>
            <div className="text-gray-500 mt-3"># 4. Restart Futuro</div>
            <div>make dev</div>
          </div>
        </section>

      </div>

      {/* Pull modal */}
      {pulling && (
        <PullModal
          model={pulling}
          onDone={() => { loadAll(); }}
          onClose={() => setPulling(null)}
        />
      )}
    </div>
  );
}
