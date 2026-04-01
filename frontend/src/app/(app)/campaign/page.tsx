"use client";

import { useEffect, useState } from "react";
import { Plus, ExternalLink, ChevronRight, Trash2, X } from "lucide-react";
import { campaign as campaignApi } from "@/lib/api";
import type { Company, Stage, Priority } from "@/types";
import clsx from "clsx";

const PIPELINE: Stage[] = ["RESEARCHING", "APPLIED", "SCREENING", "TECHNICAL", "ONSITE", "OFFER"];

const STAGE_COLORS: Record<string, string> = {
  RESEARCHING: "bg-gray-100 text-gray-600",
  APPLIED:     "bg-blue-100 text-blue-700",
  SCREENING:   "bg-yellow-100 text-yellow-700",
  TECHNICAL:   "bg-orange-100 text-orange-700",
  ONSITE:      "bg-purple-100 text-purple-700",
  OFFER:       "bg-green-100 text-green-700",
};

const PRIORITY_DOTS: Record<Priority, string> = {
  HIGH:   "bg-red-500",
  MEDIUM: "bg-yellow-400",
  LOW:    "bg-gray-300",
};

function daysSince(dateStr: string | null): number | null {
  if (!dateStr) return null;
  const diff = Date.now() - new Date(dateStr).getTime();
  return Math.floor(diff / 86400000);
}

function AddCompanyModal({ onAdd, onClose }: { onAdd: (c: Company) => void; onClose: () => void }) {
  const [name, setName]     = useState("");
  const [role, setRole]     = useState("");
  const [url, setUrl]       = useState("");
  const [priority, setPri]  = useState<Priority>("MEDIUM");
  const [notes, setNotes]   = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name || !role) return;
    setSaving(true);
    setError(null);
    try {
      const company = await campaignApi.create({ name, role_title: role, url: url || undefined, priority, notes: notes || undefined });
      onAdd(company);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add company");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-gray-900">Add company</h2>
          <button onClick={onClose}><X size={18} className="text-gray-400 hover:text-gray-600" /></button>
        </div>
        <form onSubmit={submit} className="px-6 py-5 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Company *</label>
              <input value={name} onChange={e => setName(e.target.value)} required className="input" placeholder="Anthropic" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Role *</label>
              <input value={role} onChange={e => setRole(e.target.value)} required className="input" placeholder="AI Engineer" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Job URL</label>
            <input value={url} onChange={e => setUrl(e.target.value)} type="url" className="input" placeholder="https://…" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Priority</label>
            <div className="flex gap-2">
              {(["HIGH","MEDIUM","LOW"] as Priority[]).map(p => (
                <button key={p} type="button" onClick={() => setPri(p)}
                  className={clsx("px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors",
                    priority === p ? "bg-futuro-500 text-white border-futuro-500" : "border-gray-200 text-gray-600 hover:border-gray-300")}>
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} className="input resize-none" rows={2} placeholder="Why this company, where you heard about it…" />
          </div>
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {error}
            </div>
          )}
          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={saving || !name || !role}
              className="flex-1 py-2 bg-futuro-500 hover:bg-futuro-600 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors">
              {saving ? "Adding…" : "Add company"}
            </button>
            <button type="button" onClick={onClose} className="px-4 py-2 border border-gray-200 text-gray-600 text-sm rounded-lg hover:bg-gray-50">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function CompanyCard({ company, onStageChange, onDelete }: {
  company: Company;
  onStageChange: (id: number, stage: Stage) => void;
  onDelete: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const days = daysSince(company.updated_at);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-3 shadow-sm hover:shadow-md transition-shadow">
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={clsx("w-2 h-2 rounded-full flex-shrink-0", PRIORITY_DOTS[company.priority])} />
          <span className="font-medium text-sm text-gray-900 truncate">{company.name}</span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          {company.url && (
            <a href={company.url} target="_blank" rel="noreferrer" className="text-gray-400 hover:text-futuro-500">
              <ExternalLink size={13} />
            </a>
          )}
          <button onClick={() => onDelete(company.id)} className="text-gray-300 hover:text-red-400 ml-1">
            <Trash2 size={13} />
          </button>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-0.5 pl-3.5 truncate">{company.role_title}</p>

      {/* Days & expand */}
      <div className="flex items-center justify-between mt-2 pl-3.5">
        <span className="text-xs text-gray-400">{days !== null ? `${days}d` : ""}</span>
        <button onClick={() => setExpanded(!expanded)} className="text-gray-400 hover:text-gray-600">
          <ChevronRight size={13} className={clsx("transition-transform", expanded && "rotate-90")} />
        </button>
      </div>

      {/* Expanded: move stage */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          <p className="text-xs text-gray-400 mb-1.5">Move to stage:</p>
          <div className="flex flex-wrap gap-1">
            {PIPELINE.filter(s => s !== company.stage).map(s => (
              <button key={s} onClick={() => { onStageChange(company.id, s); setExpanded(false); }}
                className="text-xs px-2 py-0.5 rounded-full border border-gray-200 text-gray-600 hover:bg-gray-100 transition-colors">
                {s.charAt(0) + s.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
          {company.notes && <p className="text-xs text-gray-500 mt-2 italic">{company.notes}</p>}
        </div>
      )}
    </div>
  );
}

export default function CompanyPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [stats,     setStats]     = useState<{ total_active: number; response_rate: number; offers: number } | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [showAdd,   setShowAdd]   = useState(false);

  useEffect(() => {
    Promise.all([campaignApi.list(), campaignApi.stats()])
      .then(([cs, st]) => { setCompanies(cs); setStats(st); })
      .finally(() => setLoading(false));
  }, []);

  async function handleStageChange(id: number, stage: Stage) {
    const updated = await campaignApi.updateStage(id, stage);
    setCompanies(cs => cs.map(c => c.id === id ? updated : c));
  }

  async function handleDelete(id: number) {
    if (!confirm("Remove this company?")) return;
    await campaignApi.delete(id);
    setCompanies(cs => cs.filter(c => c.id !== id));
  }

  const byStage = (stage: Stage) => companies.filter(c => c.stage === stage);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-4">
          <h1 className="font-semibold text-gray-900">Company</h1>
          {stats && (
            <span className="text-xs text-gray-500">
              {stats.total_active} active · {Math.round(stats.response_rate * 100)}% response rate · {stats.offers} offers
            </span>
          )}
        </div>
        <button onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-futuro-500 hover:bg-futuro-600 text-white text-sm rounded-lg transition-colors">
          <Plus size={15}/> Add company
        </button>
      </div>

      {/* Board */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">Loading…</div>
        ) : (
          <div className="flex gap-3 p-4 h-full min-w-max">
            {PIPELINE.map(stage => {
              const cols = byStage(stage);
              return (
                <div key={stage} className="flex flex-col w-52 flex-shrink-0">
                  {/* Column header */}
                  <div className="flex items-center justify-between mb-2 px-1">
                    <span className={clsx("text-xs font-medium px-2 py-0.5 rounded-full", STAGE_COLORS[stage])}>
                      {stage.charAt(0) + stage.slice(1).toLowerCase()}
                    </span>
                    <span className="text-xs text-gray-400">{cols.length}</span>
                  </div>
                  {/* Cards */}
                  <div className="flex-1 overflow-y-auto scrollbar-thin space-y-2 pb-2">
                    {cols.map(c => (
                      <CompanyCard
                        key={c.id}
                        company={c}
                        onStageChange={handleStageChange}
                        onDelete={handleDelete}
                      />
                    ))}
                    {cols.length === 0 && (
                      <div className="text-xs text-gray-300 text-center py-6">—</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {showAdd && (
        <AddCompanyModal
          onAdd={c => setCompanies(cs => [c, ...cs])}
          onClose={() => setShowAdd(false)}
        />
      )}

      <style jsx global>{`
        .input {
          width: 100%;
          padding: 0.375rem 0.75rem;
          border: 1px solid #e5e7eb;
          border-radius: 0.5rem;
          font-size: 0.875rem;
          outline: none;
          transition: box-shadow 0.15s;
        }
        .input:focus {
          box-shadow: 0 0 0 2px #6366f1;
          border-color: transparent;
        }
      `}</style>
    </div>
  );
}
