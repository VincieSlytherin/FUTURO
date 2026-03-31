"use client";

import { useEffect, useState } from "react";
import { Cpu, Cloud, AlertCircle, RefreshCw } from "lucide-react";
import { req } from "@/lib/api-internal";
import clsx from "clsx";

interface ProviderEntry {
  provider: string;
  model: string;
}

interface ProviderStatusData {
  routing: Record<string, ProviderEntry>;
  ollama?: {
    enabled: boolean;
    base_url: string;
    chat_model: string;
    embed_model: string;
  };
}

interface HealthData {
  [provider: string]: {
    ok: boolean;
    model: string;
    detail: string;
    embed_model?: string;
    available_models?: string[];
  };
}

const PROVIDER_ICONS: Record<string, React.ReactNode> = {
  ollama: <Cpu size={11} />,
  claude: <Cloud size={11} />,
};

const TASK_LABELS: Record<string, string> = {
  chat:     "Chat",
  classify: "Classify",
  score:    "Score",
  embed:    "Embed",
};

export default function ProviderStatus() {
  const [status,  setStatus]  = useState<ProviderStatusData | null>(null);
  const [health,  setHealth]  = useState<HealthData | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [s, h] = await Promise.all([
        fetch("/api/providers/status", {
          headers: { Authorization: `Bearer ${getCookie("futuro_token")}` },
        }).then(r => r.json()),
        fetch("/api/providers/health", {
          headers: { Authorization: `Bearer ${getCookie("futuro_token")}` },
        }).then(r => r.json()),
      ]);
      setStatus(s);
      setHealth(h);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, []);

  if (!status) return null;

  // Derive dominant provider for the compact indicator
  const chatProvider = status.routing?.chat?.provider ?? "unknown";
  const allOk = health ? Object.values(health).every(h => h.ok) : null;

  return (
    <div className="px-3 pb-3">
      <button
        onClick={() => { setExpanded(e => !e); if (!expanded) load(); }}
        className={clsx(
          "w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors",
          expanded ? "bg-gray-100" : "hover:bg-gray-50"
        )}
      >
        {/* Provider icon */}
        <span className={clsx(
          "flex-shrink-0",
          allOk === true ? "text-green-500" :
          allOk === false ? "text-red-400" : "text-gray-400"
        )}>
          {chatProvider === "ollama" ? <Cpu size={12} /> : <Cloud size={12} />}
        </span>

        <span className="flex-1 text-left text-gray-500 truncate">
          {chatProvider === "ollama"
            ? status.ollama?.chat_model ?? "Local"
            : "Claude"}
        </span>

        {allOk === false && <AlertCircle size={11} className="text-red-400 flex-shrink-0" />}
        {loading && <RefreshCw size={10} className="text-gray-400 animate-spin flex-shrink-0" />}
      </button>

      {/* Expanded panel */}
      {expanded && (
        <div className="mt-1 border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm">
          {/* Health summary */}
          {health && Object.entries(health).map(([name, h]) => (
            <div key={name} className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-0">
              <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0",
                h.ok ? "bg-green-500" : "bg-red-400")} />
              <span className="text-xs text-gray-700 font-medium capitalize">{name}</span>
              <span className="text-xs text-gray-400 truncate ml-auto">{h.model}</span>
            </div>
          ))}

          {/* Task routing */}
          <div className="px-3 py-2 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-500 mb-1.5">Task routing</p>
            <div className="space-y-1">
              {Object.entries(status.routing ?? {}).map(([task, entry]) => (
                <div key={task} className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">{TASK_LABELS[task] ?? task}</span>
                  <div className="flex items-center gap-1 text-gray-600">
                    <span className="text-gray-400">{PROVIDER_ICONS[entry.provider]}</span>
                    <span className="font-mono text-gray-500 truncate max-w-[90px]">{entry.model}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Pull hint if Ollama not ok */}
          {health && Object.entries(health).some(([, h]) => !h.ok && h.detail?.includes("ollama")) && (
            <div className="px-3 py-2 bg-amber-50 border-t border-amber-100">
              <p className="text-xs text-amber-700">
                Run: <code className="font-mono">ollama serve</code>
              </p>
            </div>
          )}

          <div className="px-3 py-1.5 border-t border-gray-100 flex justify-end">
            <button onClick={load} className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1">
              <RefreshCw size={10}/> refresh
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function getCookie(name: string): string {
  if (typeof document === "undefined") return "";
  const m = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return m ? m[2] : "";
}
