// ── Project ────────────────────────────────────────────────
export type ProjectStatus =
  | "pending"
  | "planning"
  | "building"
  | "reviewing"
  | "paused"
  | "frozen"
  | "completed"
  | "error";

export interface Project {
  id: string;
  name: string;
  description: string;
  status: ProjectStatus;
  plan_md: string | null;
  stack_config: StackConfig | null;
  container_id: string | null;
  preview_port: number | null;
  created_at: string;
  updated_at: string;
}

export interface StackConfig {
  framework: string;
  language: string;
  styling: string;
  package_manager: string;
  [key: string]: string;
}

// ── Chat ──────────────────────────────────────────────────
export type MessageRole = "user" | "architect" | "system";

export interface ChatMessage {
  id: string;
  project_id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
}

// ── Plan ──────────────────────────────────────────────────
export interface PlanTask {
  index: number;
  text: string;
  completed: boolean;
  phase: string | null;
}

export interface PlanProgress {
  total: number;
  completed: number;
  percentage: number;
}

// ── Builder ───────────────────────────────────────────────
export type BuilderStatus = "SUCCESS" | "BLOCKER" | "AMBIGUITY" | "SILENT_DECISION";

export interface BuilderLog {
  project_id: string;
  task_index: number;
  task_text: string;
  status: BuilderStatus;
  output: string;
  error_detail: string | null;
  timestamp: string;
}

// ── Session ───────────────────────────────────────────────
export interface Session {
  id: string;
  project_id: string;
  started_at: string;
  ended_at: string | null;
  status: string;
}

// ── Task Log ──────────────────────────────────────────────
export interface TaskLog {
  id: string;
  session_id: string;
  task_index: number;
  task_text: string;
  status: BuilderStatus;
  output: string;
  error_detail: string | null;
  created_at: string;
}

// ── WebSocket Events ──────────────────────────────────────
export interface WsArchitectMessage {
  project_id: string;
  content: string;
  is_streaming: boolean;
}

export interface WsBuilderLog {
  project_id: string;
  task_index: number;
  task_text: string;
  output: string;
  status: BuilderStatus;
}

export interface WsStatusUpdate {
  project_id: string;
  status: ProjectStatus;
  detail?: string;
}

export interface WsHumanRequired {
  project_id: string;
  reason: string;
  context?: string;
}

export interface WsPlanUpdated {
  project_id: string;
  plan_md: string;
}

// ── API Responses ─────────────────────────────────────────
export interface ApiResponse<T> {
  data: T;
  error?: string;
}

export interface ProjectCreateRequest {
  name: string;
  description: string;
}

export interface ProjectStartRequest {
  project_id: string;
}

export interface ChatSendRequest {
  project_id: string;
  message: string;
}

export interface ApproveRequest {
  project_id: string;
  feedback?: string;
}
