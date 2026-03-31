// ── Scout (append to existing api.ts) ────────────────────────────────────────

export interface ScoutConfig {
  id: number;
  name: string;
  search_term: string;
  location: string;
  distance_miles: number;
  sites: string;
  results_wanted: number;
  hours_old: number;
  is_remote: boolean | null;
  min_score: number;
  schedule_hours: number;
  is_active: boolean;
  last_run_at: string | null;
  created_at: string;
}

export interface JobListing {
  id: number;
  title: string;
  company: string;
  location: string | null;
  is_remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  description: string | null;
  site: string;
  date_posted: string | null;
  job_type: string | null;
  job_url: string;
  score: number | null;
  score_summary: string | null;
  score_pros: string[];
  score_cons: string[];
  sponsorship_likely: boolean | null;
  status: string;
  user_note: string | null;
  discovered_at: string;
  seen_at: string | null;
}

export interface ScoutStats {
  total_found: number;
  new_unseen: number;
  high_score: number;
  added_to_pipeline: number;
  avg_score: number | null;
  active_configs: number;
}

export const scout = {
  // Configs
  listConfigs: () => req<ScoutConfig[]>("/api/scout/configs"),
  createConfig: (data: Omit<ScoutConfig, "id" | "created_at" | "last_run_at">) =>
    req<ScoutConfig>("/api/scout/configs", { method: "POST", body: JSON.stringify(data) }),
  updateConfig: (id: number, data: Partial<ScoutConfig>) =>
    req<ScoutConfig>(`/api/scout/configs/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteConfig: (id: number) =>
    req(`/api/scout/configs/${id}`, { method: "DELETE" }),
  runConfig: (id: number) =>
    req<{ queued: boolean; message: string }>(`/api/scout/configs/${id}/run`, { method: "POST" }),
  listRuns: (id: number) =>
    req<Array<{ id: number; status: string; started_at: string; jobs_found: number; jobs_new: number; jobs_scored: number; error_msg: string | null }>>(`/api/scout/configs/${id}/runs`),

  // Jobs
  listJobs: (params: { status?: string; min_score?: number; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params.status)    qs.set("status", params.status);
    if (params.min_score) qs.set("min_score", String(params.min_score));
    if (params.limit)     qs.set("limit", String(params.limit));
    if (params.offset)    qs.set("offset", String(params.offset));
    return req<{ jobs: JobListing[]; total: number }>(`/api/scout/jobs?${qs}`);
  },
  getJob: (id: number) => req<JobListing>(`/api/scout/jobs/${id}`),
  actionJob: (id: number, status: string, note?: string) =>
    req(`/api/scout/jobs/${id}/action`, { method: "PATCH", body: JSON.stringify({ status, note }) }),
  addToPipeline: (id: number) =>
    req<{ company_id: number; company_name: string }>(`/api/scout/jobs/${id}/to-pipeline`, { method: "POST" }),

  // Stats
  stats: () => req<ScoutStats>("/api/scout/stats"),
};
