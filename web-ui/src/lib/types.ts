export type ProjectStatus =
  | "pending"
  | "planning"
  | "building"
  | "preview"
  | "ready_for_deploy"
  | "deploying"
  | "deployed"
  | "paused"
  | "frozen"
  | "error"
  | "deleted";

export type ProjectStage =
  | "intake"
  | "planning"
  | "awaiting_plan_approval"
  | "repo_preparing"
  | "scaffolding"
  | "building"
  | "awaiting_preview_approval"
  | "ready_for_deploy"
  | "deploying"
  | "deployed"
  | "frozen"
  | "error";

export interface StackConfig {
  [key: string]: unknown;
}

export interface DeployTargetSummary {
  host: string | null;
  port: number | null;
  user: string | null;
  deploy_path: string | null;
  auth_reference: string | null;
  app_url: string | null;
  health_path: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  intake_text: string;
  intake_source: string;
  source_ref: string | null;
  status: ProjectStatus;
  project_stage: ProjectStage;
  plan_md: string | null;
  stack_config: StackConfig;
  repo_name: string | null;
  repo_url: string | null;
  repo_clone_url: string | null;
  default_branch: string | null;
  develop_branch: string | null;
  feature_branch: string | null;
  repo_ready: boolean;
  container_id: string | null;
  port: number | null;
  preview_url: string | null;
  preview_status: string | null;
  ci_status: string;
  ci_run_id: string | null;
  ci_run_url: string | null;
  deploy_status: string | null;
  deploy_run_url: string | null;
  deploy_commit_sha: string | null;
  github_environment_name: string | null;
  last_workflow_sync_at: string | null;
  deploy_target_summary: DeployTargetSummary | null;
  plan_approved: boolean;
  preview_approved: boolean;
  created_at: string;
  updated_at: string;
}

export type MessageRole = "user" | "architect" | "system";

export interface ChatMessage {
  id: string;
  project_id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
}

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

export interface Session {
  id: string;
  project_id: string;
  started_at: string;
  ended_at: string | null;
  phase: string;
}

export interface DeployRun {
  id: string;
  project_id: string;
  status: string;
  branch: string;
  output: string;
  summary: Record<string, unknown>;
  created_at: string;
  deployed_at: string | null;
}

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
  stage: ProjectStage;
  progress?: {
    total?: number;
    completed?: number;
  };
  preview_url?: string | null;
}

export interface WsHumanRequired {
  project_id: string;
  reason: string;
  stage?: ProjectStage;
}

export interface WsPlanUpdated {
  project_id: string;
  plan_md: string;
}

export interface PlanProgress {
  total: number;
  completed: number;
  percentage: number;
}

export interface ProjectCreateRequest {
  name: string;
  intake_text: string;
  source?: string;
  source_ref?: string | null;
}

export interface DeployTargetRequest {
  host: string;
  port?: number;
  user: string;
  deploy_path: string;
  auth_reference?: string;
  ssh_private_key: string;
  known_hosts?: string;
  env_content?: string;
  app_url?: string;
  health_path?: string;
}
