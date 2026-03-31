"use client";

import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { campaign as campaignApi } from "@/lib/api";
import type { Company } from "@/types";

export default function InterviewsPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [showAdd,   setShowAdd]   = useState(false);

  useEffect(() => {
    campaignApi.list().then(setCompanies);
  }, []);

  const withInterviews = companies.filter(c =>
    ["SCREENING","TECHNICAL","ONSITE"].includes(c.stage)
  );

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
          </div>
        )}
      </div>
    </div>
  );
}
