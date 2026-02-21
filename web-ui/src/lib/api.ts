import type {
  Project,
  ProjectCreateRequest,
  ChatMessage,
  TaskLog,
  Session,
  PlanProgress,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Helper ────────────────────────────────────────────────
async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// ── Projects ──────────────────────────────────────────────
export async function getProjects(): Promise<Project[]> {
  return request("/api/projects");
}

export async function getProject(id: string): Promise<Project> {
  return request(`/api/projects/${id}`);
}

export async function createProject(
  data: ProjectCreateRequest
): Promise<Project> {
  return request("/api/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteProject(id: string): Promise<void> {
  return request(`/api/projects/${id}`, { method: "DELETE" });
}

// ── Orchestration ─────────────────────────────────────────
export async function startProject(projectId: string): Promise<{ status: string }> {
  return request(`/api/projects/${projectId}/start`, {
    method: "POST",
  });
}

export async function stopProject(projectId: string): Promise<{ status: string }> {
  return request(`/api/projects/${projectId}/stop`, {
    method: "POST",
  });
}

export async function approveProject(
  projectId: string,
  feedback?: string
): Promise<{ status: string }> {
  return request(`/api/projects/${projectId}/approve`, {
    method: "POST",
    body: JSON.stringify({ feedback }),
  });
}

// ── Plan ──────────────────────────────────────────────────
export async function getProjectPlan(
  projectId: string
): Promise<{ plan_md: string }> {
  return request(`/api/projects/${projectId}/plan`);
}

export async function updateProjectPlan(
  projectId: string,
  planMd: string
): Promise<{ status: string }> {
  return request(`/api/projects/${projectId}/plan`, {
    method: "PUT",
    body: JSON.stringify({ plan_md: planMd }),
  });
}

// ── Chat History ──────────────────────────────────────────
export async function getChatHistory(
  projectId: string
): Promise<ChatMessage[]> {
  return request(`/api/projects/${projectId}/history`);
}

// ── Logs ──────────────────────────────────────────────────
export async function getProjectLogs(
  projectId: string
): Promise<TaskLog[]> {
  return request(`/api/projects/${projectId}/logs`);
}

// ── Sessions ──────────────────────────────────────────────
export async function getProjectSessions(
  projectId: string
): Promise<Session[]> {
  return request(`/api/projects/${projectId}/sessions`);
}

// ── Preview ───────────────────────────────────────────────
export async function getPreviewUrl(
  projectId: string
): Promise<{ url: string | null }> {
  return request(`/api/projects/${projectId}/preview-url`);
}

// ── Rollback ──────────────────────────────────────────────
export async function rollbackProject(
  projectId: string,
  checkpointId: string
): Promise<{ status: string }> {
  return request(`/api/projects/${projectId}/rollback`, {
    method: "POST",
    body: JSON.stringify({ checkpoint_id: checkpointId }),
  });
}
