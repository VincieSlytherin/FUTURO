"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Search, Play, Settings, Plus, ExternalLink,
  ChevronRight, ChevronDown, Bookmark, Briefcase,
  X, CheckCircle, Eye, EyeOff, Zap, Clock, RefreshCw,
} from "lucide-react";
import { scout } from "@/lib/scout-api";
import type { ScoutConfig, JobListing, ScoutStats } from "@/lib/scout-api";
import clsx from "clsx";

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-xs text-gray-400">—</span>;
  const color =
    score >= 80 ? "bg-green-100 text-green-700 border-green-200" :
    score >= 65 ? "bg-blue-100  text-blue-700  border-blue-200" :
    score >= 50 ? "bg-yellow-100 text-yellow-700 border-yellow-200" :
                  "bg-gray-100  text-gray-500  border-gray-200";
  return (
    <span className={clsx("text-xs font-semibold px-2 py-0.5 rounded-full border", color)}>
      {score}
    </span>
  );
}

// ── Sponsorship pill ──────────────────────────────────────────────────────────

function SponsorPill({ likely }: { likely: boolean | null }) {
  if (likely === null) return null;
  return likely ? (
    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">H-1B ✓</span>
  ) : (
    <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">No sponsor</span>
  );
}

// ── Salary display ────────────────────────────────────────────────────────────

function SalaryRange({ job }: { job: JobListing }) {
  if (!job.salary_min && !job.salary_max) return null;
  const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
  const text = job.salary_min && job.salary_max
    ? `${fmt(job.salary_min)} – ${fmt(job.salary_max)}`
    : job.salary_min ? `${fmt(job.salary_min)}+` : `up to ${fmt(job.salary_max!)}`;
  return <span className="text-xs text-gray-500">{text}</span>;
}

// ── Job card ──────────────────────────────────────────────────────────────────

function JobCard({
  job, onAction, onToPipeline
}: {
  job: JobListing;
  onAction: (id: number, status: string) => void;
  onToPipeline: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [actioning, setActioning] = useState(false);

  async function doAction(status: string) {
    setActioning(true);
    await onAction(job.id, status);
    setActioning(false);
  }

  const siteColor: Record<string, string> = {
    linkedin:    "text-blue-600",
    indeed:      "text-indigo-600",
    glassdoor:   "text-green-600",
    ziprecruiter: "text-orange-600",
  };

  return (
    <div className={clsx(
      "bg-white border rounded-xl overflow-hidden transition-shadow hover:shadow-md",
      job.status === "NEW" ? "border-gray-200" : "border-gray-100 opacity-75"
    )}>
      {/* Main row */}
      <div className="px-4 py-3">
        <div className="flex items-start gap-3">
          {/* Score */}
          <div className="flex-shrink-0 flex flex-col items-center gap-1 pt-0.5">
            <ScoreBadge score={job.score} />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <a
                  href={job.job_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-sm text-gray-900 hover:text-futuro-600 line-clamp-1"
                >
                  {job.title}
                </a>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span className="text-sm text-gray-600">{job.company}</span>
                  <span className="text-gray-300">·</span>
                  <span className="text-xs text-gray-400">{job.location || "Location not listed"}</span>
                  {job.is_remote && (
                    <span className="text-xs bg-teal-50 text-teal-700 px-1.5 py-0.5 rounded">Remote</span>
                  )}
                </div>
              </div>
              <div className="flex-shrink-0 flex items-center gap-1.5">
                <SponsorPill likely={job.sponsorship_likely} />
                <SalaryRange job={job} />
                <span className={clsx("text-xs capitalize", siteColor[job.site] ?? "text-gray-400")}>
                  {job.site}
                </span>
              </div>
            </div>

            {/* Score summary */}
            {job.score_summary && (
              <p className="text-xs text-gray-500 mt-1.5 line-clamp-2 leading-relaxed">
                {job.score_summary}
              </p>
            )}

            {/* Expand toggle */}
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 mt-1.5 transition-colors"
            >
              {expanded ? <ChevronDown size={12}/> : <ChevronRight size={12}/>}
              {expanded ? "Less" : "Details + pros/cons"}
            </button>
          </div>

          {/* Action buttons */}
          {job.status === "NEW" && (
            <div className="flex-shrink-0 flex flex-col gap-1">
              <button
                onClick={() => onToPipeline(job.id)}
                disabled={actioning}
                title="Add to campaign pipeline"
                className="p-1.5 text-gray-400 hover:text-futuro-600 hover:bg-futuro-50 rounded-lg transition-colors"
              >
                <Briefcase size={14}/>
              </button>
              <button
                onClick={() => doAction("SAVED")}
                disabled={actioning}
                title="Save for later"
                className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
              >
                <Bookmark size={14}/>
              </button>
              <button
                onClick={() => doAction("DISMISSED")}
                disabled={actioning}
                title="Dismiss"
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              >
                <X size={14}/>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3 bg-gray-50 space-y-3">
          {/* Pros / Cons */}
          {(job.score_pros.length > 0 || job.score_cons.length > 0) && (
            <div className="grid grid-cols-2 gap-3">
              {job.score_pros.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-green-700 mb-1">Why it fits</p>
                  <ul className="space-y-0.5">
                    {job.score_pros.map((p, i) => (
                      <li key={i} className="text-xs text-gray-600 flex gap-1">
                        <span className="text-green-500 flex-shrink-0">✓</span>{p}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {job.score_cons.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-red-600 mb-1">Watch out for</p>
                  <ul className="space-y-0.5">
                    {job.score_cons.map((c, i) => (
                      <li key={i} className="text-xs text-gray-600 flex gap-1">
                        <span className="text-red-400 flex-shrink-0">✗</span>{c}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Description snippet */}
          {job.description && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-1">Description</p>
              <p className="text-xs text-gray-600 leading-relaxed line-clamp-4">{job.description}</p>
            </div>
          )}

          {/* Actions row */}
          <div className="flex items-center gap-2 pt-1">
            <a
              href={job.job_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 text-xs text-futuro-600 hover:underline"
            >
              <ExternalLink size={11}/> View job
            </a>
            {job.status === "NEW" && (
              <>
                <button onClick={() => onToPipeline(job.id)}
                  className="flex items-center gap-1 text-xs text-futuro-600 hover:underline ml-3">
                  <Briefcase size={11}/> Add to pipeline
                </button>
                <button onClick={() => doAction("APPLIED")}
                  className="flex items-center gap-1 text-xs text-green-600 hover:underline ml-3">
                  <CheckCircle size={11}/> Mark applied
                </button>
              </>
            )}
            <span className="ml-auto text-xs text-gray-400">{job.date_posted}</span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Config card ───────────────────────────────────────────────────────────────

function ConfigCard({
  config, onRun, onToggle, onDelete,
}: {
  config: ScoutConfig;
  onRun: (id: number) => void;
  onToggle: (id: number, active: boolean) => void;
  onDelete: (id: number) => void;
}) {
  const [running, setRunning] = useState(false);

  async function handleRun() {
    setRunning(true);
    try { await onRun(config.id); } finally {
      setTimeout(() => setRunning(false), 3000);
    }
  }

  return (
    <div className={clsx(
      "border rounded-xl p-3 text-sm",
      config.is_active ? "border-futuro-200 bg-futuro-50/50" : "border-gray-200 bg-gray-50"
    )}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx("w-1.5 h-1.5 rounded-full flex-shrink-0",
              config.is_active ? "bg-green-500" : "bg-gray-400")}/>
            <span className="font-medium text-gray-900 truncate">{config.name}</span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5 pl-3.5">
            "{config.search_term}" · {config.location} · every {config.schedule_hours}h
          </p>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={handleRun}
            disabled={running}
            title="Run now"
            className="p-1.5 text-gray-400 hover:text-futuro-600 hover:bg-white rounded-lg transition-colors"
          >
            <Play size={13} className={running ? "animate-pulse text-futuro-500" : ""} />
          </button>
          <button
            onClick={() => onToggle(config.id, !config.is_active)}
            title={config.is_active ? "Pause" : "Activate"}
            className="p-1.5 text-gray-400 hover:text-amber-600 hover:bg-white rounded-lg transition-colors"
          >
            {config.is_active ? <EyeOff size={13}/> : <Eye size={13}/>}
          </button>
          <button
            onClick={() => { if (confirm(`Delete "${config.name}"?`)) onDelete(config.id); }}
            className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-white rounded-lg transition-colors"
          >
            <X size={13}/>
          </button>
        </div>
      </div>
      {config.last_run_at && (
        <p className="text-xs text-gray-400 mt-1.5 pl-3.5 flex items-center gap-1">
          <Clock size={10}/> Last run: {new Date(config.last_run_at).toLocaleString()}
        </p>
      )}
    </div>
  );
}

// ── Add config modal ──────────────────────────────────────────────────────────

function AddConfigModal({ onAdd, onClose }: { onAdd: (c: ScoutConfig) => void; onClose: () => void }) {
  const [form, setForm] = useState({
    name: "", search_term: "AI Engineer", location: "San Francisco, CA",
    distance_miles: 50, sites: "linkedin,indeed,glassdoor",
    results_wanted: 25, hours_old: 72, is_remote: null as boolean | null,
    min_score: 60, schedule_hours: 12, is_active: true,
  });
  const [saving, setSaving] = useState(false);

  function set(key: string, val: unknown) { setForm(f => ({ ...f, [key]: val })); }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const c = await scout.createConfig(form as any);
      onAdd(c);
      onClose();
    } finally { setSaving(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white">
          <h2 className="font-semibold text-gray-900">New scout config</h2>
          <button onClick={onClose}><X size={18} className="text-gray-400" /></button>
        </div>
        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          <div>
            <label className="label">Name</label>
            <input value={form.name} onChange={e => set("name", e.target.value)} required
              className="input" placeholder="Bay Area AI roles" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Search term</label>
              <input value={form.search_term} onChange={e => set("search_term", e.target.value)} required
                className="input" placeholder="AI Engineer" />
            </div>
            <div>
              <label className="label">Location</label>
              <input value={form.location} onChange={e => set("location", e.target.value)}
                className="input" placeholder="San Francisco, CA" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">Min score</label>
              <input type="number" min={0} max={100} value={form.min_score}
                onChange={e => set("min_score", +e.target.value)} className="input" />
            </div>
            <div>
              <label className="label">Results</label>
              <input type="number" min={5} max={100} value={form.results_wanted}
                onChange={e => set("results_wanted", +e.target.value)} className="input" />
            </div>
            <div>
              <label className="label">Run every (h)</label>
              <input type="number" min={1} max={168} value={form.schedule_hours}
                onChange={e => set("schedule_hours", +e.target.value)} className="input" />
            </div>
          </div>
          <div>
            <label className="label">Sites (CSV)</label>
            <input value={form.sites} onChange={e => set("sites", e.target.value)}
              className="input" placeholder="linkedin,indeed,glassdoor" />
          </div>
          <div>
            <label className="label">Remote</label>
            <div className="flex gap-2">
              {([["Any", null], ["Remote only", true], ["On-site only", false]] as const).map(([label, val]) => (
                <button key={label} type="button" onClick={() => set("is_remote", val)}
                  className={clsx("px-3 py-1.5 rounded-lg text-xs border transition-colors",
                    form.is_remote === val
                      ? "bg-futuro-500 text-white border-futuro-500"
                      : "border-gray-200 text-gray-600 hover:border-gray-300")}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving || !form.name || !form.search_term}
              className="flex-1 py-2 bg-futuro-500 hover:bg-futuro-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
              {saving ? "Creating…" : "Create config"}
            </button>
            <button type="button" onClick={onClose}
              className="px-4 py-2 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

type StatusFilter = "NEW" | "SAVED" | "PIPELINE" | "DISMISSED" | "ALL";

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: "NEW",      label: "New"       },
  { key: "SAVED",    label: "Saved"     },
  { key: "PIPELINE", label: "Pipeline"  },
  { key: "DISMISSED",label: "Dismissed" },
  { key: "ALL",      label: "All"       },
];

export default function JobsPage() {
  const [jobs,      setJobs]       = useState<JobListing[]>([]);
  const [configs,   setConfigs]    = useState<ScoutConfig[]>([]);
  const [stats,     setStats]      = useState<ScoutStats | null>(null);
  const [loading,   setLoading]    = useState(true);
  const [statusFilter, setStatus]  = useState<StatusFilter>("NEW");
  const [minScore,  setMinScore]   = useState(0);
  const [showPanel, setShowPanel]  = useState(false);
  const [showAdd,   setShowAdd]    = useState(false);
  const [total,     setTotal]      = useState(0);
  const [page,      setPage]       = useState(0);
  const PAGE_SIZE = 30;

  const loadJobs = useCallback(async (status: StatusFilter, score: number, p: number) => {
    setLoading(true);
    const data = await scout.listJobs({ status, min_score: score, limit: PAGE_SIZE, offset: p * PAGE_SIZE });
    setJobs(data.jobs);
    setTotal(data.total);
    setLoading(false);
  }, []);

  useEffect(() => {
    setPage(0);
    loadJobs(statusFilter, minScore, 0);
  }, [statusFilter, minScore, loadJobs]);

  useEffect(() => {
    Promise.all([scout.listConfigs(), scout.stats()]).then(([cs, st]) => {
      setConfigs(cs);
      setStats(st);
    });
  }, []);

  async function handleAction(id: number, status: string) {
    await scout.actionJob(id, status);
    setJobs(js => js.map(j => j.id === id ? { ...j, status } : j));
  }

  async function handleToPipeline(id: number) {
    const result = await scout.addToPipeline(id);
    setJobs(js => js.map(j => j.id === id ? { ...j, status: "PIPELINE" } : j));
    alert(`Added ${result.company_name} to your campaign pipeline!`);
  }

  async function handleRun(configId: number) {
    const result = await scout.runConfig(configId);
    if (result.queued) {
      setTimeout(() => loadJobs(statusFilter, minScore, page), 8000);
    }
  }

  async function handleToggle(configId: number, active: boolean) {
    const updated = await scout.updateConfig(configId, { is_active: active });
    setConfigs(cs => cs.map(c => c.id === configId ? updated : c));
  }

  async function handleDeleteConfig(configId: number) {
    await scout.deleteConfig(configId);
    setConfigs(cs => cs.filter(c => c.id !== configId));
  }

  const newCount = stats?.new_unseen ?? 0;

  return (
    <div className="flex h-full overflow-hidden">
      {/* Main column */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex-shrink-0 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <h1 className="font-semibold text-gray-900">Jobs</h1>
              {stats && (
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  {newCount > 0 && (
                    <span className="bg-futuro-500 text-white px-2 py-0.5 rounded-full font-medium">
                      {newCount} new
                    </span>
                  )}
                  <span>{stats.high_score} high-score</span>
                  <span>avg {stats.avg_score ?? "—"}/100</span>
                  <span>{stats.active_configs} active scouts</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowPanel(!showPanel)}
                className={clsx(
                  "flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg transition-colors",
                  showPanel ? "bg-gray-100 border-gray-300 text-gray-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"
                )}
              >
                <Settings size={14}/> Scouts
              </button>
              <button
                onClick={() => loadJobs(statusFilter, minScore, page)}
                className="p-1.5 text-gray-400 hover:text-gray-600 border border-gray-200 rounded-lg"
              >
                <RefreshCw size={14}/>
              </button>
            </div>
          </div>

          {/* Tabs + score filter */}
          <div className="flex items-center justify-between">
            <div className="flex gap-0.5">
              {STATUS_TABS.map(t => (
                <button key={t.key} onClick={() => setStatus(t.key)}
                  className={clsx("px-3 py-1.5 text-xs rounded-lg transition-colors",
                    statusFilter === t.key
                      ? "bg-futuro-500 text-white"
                      : "text-gray-600 hover:bg-gray-100")}>
                  {t.label}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span>Min score:</span>
              <input type="range" min={0} max={90} step={10} value={minScore}
                onChange={e => setMinScore(+e.target.value)}
                className="w-20 accent-futuro-500" />
              <span className="w-6 text-center">{minScore || "—"}</span>
            </div>
          </div>
        </div>

        {/* Jobs list */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-2">
          {loading && (
            <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
              Scanning…
            </div>
          )}

          {!loading && jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <Zap size={32} className="text-gray-300 mb-3"/>
              <p className="text-gray-500 text-sm font-medium">
                {configs.length === 0
                  ? "No scouts configured yet"
                  : statusFilter === "NEW"
                    ? "No new jobs found — try running a scout"
                    : "Nothing here"}
              </p>
              <p className="text-gray-400 text-xs mt-1">
                {configs.length === 0
                  ? "Create a scout config to start scanning for jobs automatically"
                  : "Trigger a manual scan or wait for the next scheduled run"}
              </p>
              {configs.length === 0 && (
                <button onClick={() => { setShowPanel(true); setShowAdd(true); }}
                  className="mt-4 px-4 py-2 bg-futuro-500 text-white text-sm rounded-lg hover:bg-futuro-600 transition-colors">
                  Create first scout
                </button>
              )}
            </div>
          )}

          {!loading && jobs.map(j => (
            <JobCard key={j.id} job={j} onAction={handleAction} onToPipeline={handleToPipeline} />
          ))}

          {/* Pagination */}
          {!loading && total > PAGE_SIZE && (
            <div className="flex items-center justify-center gap-3 pt-4 text-sm">
              <button disabled={page === 0}
                onClick={() => { const p = page - 1; setPage(p); loadJobs(statusFilter, minScore, p); }}
                className="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">
                ← Prev
              </button>
              <span className="text-gray-500">{page + 1} / {Math.ceil(total / PAGE_SIZE)}</span>
              <button disabled={(page + 1) * PAGE_SIZE >= total}
                onClick={() => { const p = page + 1; setPage(p); loadJobs(statusFilter, minScore, p); }}
                className="px-3 py-1.5 border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-gray-50">
                Next →
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Scout config panel */}
      {showPanel && (
        <div className="w-72 flex-shrink-0 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b bg-white sticky top-0">
            <h3 className="font-medium text-gray-900 text-sm">Scout configs</h3>
            <div className="flex gap-1">
              <button onClick={() => setShowAdd(true)}
                className="p-1.5 text-gray-400 hover:text-futuro-600 hover:bg-futuro-50 rounded-lg transition-colors">
                <Plus size={14}/>
              </button>
              <button onClick={() => setShowPanel(false)}
                className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg transition-colors">
                <X size={14}/>
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2">
            {configs.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-xs text-gray-400">No configs yet.</p>
                <button onClick={() => setShowAdd(true)}
                  className="mt-2 text-xs text-futuro-600 hover:underline">
                  Create one →
                </button>
              </div>
            ) : (
              configs.map(c => (
                <ConfigCard key={c.id} config={c}
                  onRun={handleRun}
                  onToggle={handleToggle}
                  onDelete={handleDeleteConfig}
                />
              ))
            )}
          </div>
        </div>
      )}

      {showAdd && (
        <AddConfigModal
          onAdd={c => setConfigs(cs => [...cs, c])}
          onClose={() => setShowAdd(false)}
        />
      )}

      <style jsx global>{`
        .label { display: block; font-size: 0.75rem; font-weight: 500; color: #374151; margin-bottom: 0.25rem; }
        .input { width: 100%; padding: 0.375rem 0.75rem; border: 1px solid #e5e7eb; border-radius: 0.5rem; font-size: 0.875rem; outline: none; }
        .input:focus { box-shadow: 0 0 0 2px #6366f1; border-color: transparent; }
      `}</style>
    </div>
  );
}
