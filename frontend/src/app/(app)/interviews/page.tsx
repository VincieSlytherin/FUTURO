"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Plus, X, Calendar, UserRound, Building2 } from "lucide-react";
import { campaign as campaignApi, interviews as interviewsApi } from "@/lib/api";
import type { Company, Interview } from "@/types";

function LogInterviewModal({
  companies,
  onClose,
  onCreated,
}: {
  companies: Company[];
  onClose: () => void;
  onCreated: (interview: Interview) => void;
}) {
  if (companies.length === 0) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
        <div className="w-full max-w-md rounded-2xl bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
            <h2 className="font-semibold text-gray-900">Log interview</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={18} />
            </button>
          </div>

          <div className="space-y-4 px-6 py-5">
            <p className="text-sm text-gray-600">
              You do not have any companies in your campaign yet, so there is nothing to attach an interview to.
            </p>
            <p className="text-sm text-gray-500">
              Add a company first, move it into Screening, Technical, or Onsite, then come back here to log the interview.
            </p>

            <div className="flex gap-3 pt-2">
              <Link
                href="/campaign"
                onClick={onClose}
                className="flex-1 rounded-lg bg-futuro-500 py-2.5 text-center text-sm font-medium text-white hover:bg-futuro-600"
              >
                Go to campaign
              </Link>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const [companyId, setCompanyId] = useState<number>(companies[0]?.id ?? 0);
  const [roundName, setRoundName] = useState("");
  const [format, setFormat] = useState("");
  const [interviewer, setInterviewer] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!companyId || !roundName.trim()) return;
    setSaving(true);
    setError("");
    try {
      const interview = await interviewsApi.create({
        company_id: companyId,
        round_name: roundName.trim(),
        format: format.trim() || undefined,
        interviewer: interviewer.trim() || undefined,
        scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null,
      });
      onCreated(interview);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not log interview");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 className="font-semibold text-gray-900">Log interview</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700">Company</label>
            <select
              value={companyId}
              onChange={(e) => setCompanyId(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              required
            >
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name} · {company.role_title}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">Round</label>
              <input
                value={roundName}
                onChange={(e) => setRoundName(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="Recruiter screen"
                required
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">Format</label>
              <input
                value={format}
                onChange={(e) => setFormat(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="Phone / Zoom / Onsite"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">Interviewer</label>
              <input
                value={interviewer}
                onChange={(e) => setInterviewer(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                placeholder="Jane Doe"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-gray-700">Scheduled time</label>
              <input
                type="datetime-local"
                value={scheduledAt}
                onChange={(e) => setScheduledAt(e.target.value)}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              />
            </div>
          </div>

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving || !companyId || !roundName.trim()}
              className="flex-1 rounded-lg bg-futuro-500 py-2.5 text-sm font-medium text-white hover:bg-futuro-600 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save interview"}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-200 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function InterviewsPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [showAdd,   setShowAdd]   = useState(false);

  useEffect(() => {
    Promise.all([campaignApi.list(), interviewsApi.list()]).then(([companyData, interviewData]) => {
      setCompanies(companyData);
      setInterviews(interviewData);
    });
  }, []);

  const withInterviews = companies.filter(c =>
    ["SCREENING","TECHNICAL","ONSITE"].includes(c.stage)
  );
  const companyById = new Map(companies.map((company) => [company.id, company]));

  return (
    <div className="flex flex-col h-full">
      <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
        <h1 className="font-semibold text-gray-900">Interviews</h1>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-futuro-500 hover:bg-futuro-600 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={15}/> Log interview
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin p-6">
        {withInterviews.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-gray-500 text-sm">No active interviews yet.</p>
            <p className="text-gray-400 text-xs mt-1">
              Move companies to Screening, Technical, or Onsite stage to see them here.
            </p>
          </div>
        ) : (
          <div className="space-y-3 max-w-2xl">
            {withInterviews.map(c => (
              <div key={c.id} className="bg-white border border-gray-200 rounded-xl p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">{c.name}</h3>
                    <p className="text-sm text-gray-500">{c.role_title} · {c.stage}</p>
                  </div>
                  <a
                    href={`/chat?prefill=I just finished an interview at ${c.name} — let's debrief`}
                    className="text-xs text-futuro-600 hover:text-futuro-700 bg-futuro-50 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Debrief →
                  </a>
                </div>
              </div>
            ))}

            {interviews.length > 0 && (
              <div className="pt-6">
                <h2 className="mb-3 text-sm font-semibold text-gray-900">Logged interviews</h2>
                <div className="space-y-3">
                  {interviews.map((interview) => {
                    const company = companyById.get(interview.company_id);
                    return (
                      <div key={interview.id} className="rounded-xl border border-gray-200 bg-white p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 text-gray-900">
                              <Building2 size={14} className="text-gray-400" />
                              <span className="font-medium">{company?.name ?? `Company #${interview.company_id}`}</span>
                            </div>
                            <p className="text-sm text-gray-600">{interview.round_name}</p>
                            <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                              {interview.format && (
                                <span className="inline-flex items-center gap-1">
                                  <UserRound size={12} />
                                  {interview.format}
                                </span>
                              )}
                              {interview.scheduled_at && (
                                <span className="inline-flex items-center gap-1">
                                  <Calendar size={12} />
                                  {new Date(interview.scheduled_at).toLocaleString()}
                                </span>
                              )}
                              {interview.interviewer && <span>Interviewer: {interview.interviewer}</span>}
                            </div>
                          </div>
                          <a
                            href={`/chat?prefill=I just finished an interview at ${company?.name ?? "this company"} — ${interview.round_name}. Help me debrief.`}
                            className="text-xs text-futuro-600 hover:text-futuro-700 bg-futuro-50 px-3 py-1.5 rounded-lg transition-colors"
                          >
                            Debrief →
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {showAdd && (
        <LogInterviewModal
          companies={companies}
          onClose={() => setShowAdd(false)}
          onCreated={(interview) => setInterviews((current) => [interview, ...current])}
        />
      )}
    </div>
  );
}
