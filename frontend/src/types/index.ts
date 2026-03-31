export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  intent?: string;
  proposedUpdates?: MemoryUpdate[];
  streaming?: boolean;
}

export interface MemoryUpdate {
  file: string;
  section: string;
  action: "append" | "replace" | "create";
  content: string;
  reason: string;
}

export type Stage =
  | "RESEARCHING"
  | "APPLIED"
  | "SCREENING"
  | "TECHNICAL"
  | "ONSITE"
  | "OFFER"
  | "CLOSED_WON"
  | "CLOSED_LOST"
  | "WITHDREW";

export type Priority = "HIGH" | "MEDIUM" | "LOW";

export interface CompanyEvent {
  id: number;
  event_type: string;
  description: string | null;
  stage_from: string | null;
  stage_to: string | null;
  happened_at: string;
}

export interface Company {
  id: number;
  name: string;
  role_title: string;
  url: string | null;
  stage: Stage;
  priority: Priority;
  notes: string | null;
  sponsorship_confirmed: boolean;
  salary_range: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  events: CompanyEvent[];
}

export interface CampaignStats {
  total_active: number;
  by_stage: Record<string, number>;
  response_rate: number;
  avg_days_to_response: number | null;
  offers: number;
}

export interface StorySearchResult {
  story_id: string;
  title: string;
  one_liner: string;
  themes: string[];
  distance: number;
  result_metric: string | null;
}

export interface MemoryFile {
  filename: string;
  last_modified: string | null;
  last_commit: string | null;
}
