import { create } from "zustand";
import type {
  Project,
  ChatMessage,
  BuilderLog,
  ProjectStatus,
  PlanProgress,
} from "@/lib/types";
import * as api from "@/lib/api";

// ── Project Store ─────────────────────────────────────────
interface ProjectState {
  // Data
  projects: Project[];
  currentProject: Project | null;
  chatMessages: ChatMessage[];
  builderLogs: BuilderLog[];
  planMd: string | null;
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;

  // Human intervention
  humanRequired: boolean;
  humanReason: string | null;

  // Progress
  progress: PlanProgress | null;

  // Actions
  setProjects: (projects: Project[]) => void;
  setCurrentProject: (project: Project | null) => void;
  updateProjectStatus: (projectId: string, status: ProjectStatus) => void;
  addChatMessage: (message: ChatMessage) => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  addBuilderLog: (log: BuilderLog) => void;
  clearBuilderLogs: () => void;
  setPlanMd: (planMd: string | null) => void;
  setConnected: (connected: boolean) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setHumanRequired: (required: boolean, reason?: string) => void;
  setProgress: (progress: PlanProgress | null) => void;

  // Async actions
  fetchProjects: () => Promise<void>;
  fetchProject: (id: string) => Promise<void>;
  createProject: (name: string, description: string) => Promise<Project>;
  startProject: (id: string) => Promise<void>;
  stopProject: (id: string) => Promise<void>;
  approveProject: (id: string, feedback?: string) => Promise<void>;
  fetchChatHistory: (projectId: string) => Promise<void>;
  fetchPlan: (projectId: string) => Promise<void>;
  updatePlan: (projectId: string, planMd: string) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  // Initial state
  projects: [],
  currentProject: null,
  chatMessages: [],
  builderLogs: [],
  planMd: null,
  isConnected: false,
  isLoading: false,
  error: null,
  humanRequired: false,
  humanReason: null,
  progress: null,

  // Setters
  setProjects: (projects) => set({ projects }),
  setCurrentProject: (project) => set({ currentProject: project }),
  updateProjectStatus: (projectId, status) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId ? { ...p, status } : p
      ),
      currentProject:
        state.currentProject?.id === projectId
          ? { ...state.currentProject, status }
          : state.currentProject,
    })),
  addChatMessage: (message) =>
    set((state) => ({
      chatMessages: [...state.chatMessages, message],
    })),
  setChatMessages: (messages) => set({ chatMessages: messages }),
  addBuilderLog: (log) =>
    set((state) => ({
      builderLogs: [...state.builderLogs, log],
    })),
  clearBuilderLogs: () => set({ builderLogs: [] }),
  setPlanMd: (planMd) => set({ planMd }),
  setConnected: (connected) => set({ isConnected: connected }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setHumanRequired: (required, reason) =>
    set({ humanRequired: required, humanReason: reason || null }),
  setProgress: (progress) => set({ progress }),

  // Async actions
  fetchProjects: async () => {
    set({ isLoading: true, error: null });
    try {
      const projects = await api.getProjects();
      set({ projects, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  fetchProject: async (id) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.getProject(id);
      set({ currentProject: project, isLoading: false });
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
    }
  },

  createProject: async (name, description) => {
    set({ isLoading: true, error: null });
    try {
      const project = await api.createProject({ name, description });
      set((state) => ({
        projects: [...state.projects, project],
        isLoading: false,
      }));
      return project;
    } catch (e: any) {
      set({ error: e.message, isLoading: false });
      throw e;
    }
  },

  startProject: async (id) => {
    set({ error: null });
    try {
      await api.startProject(id);
      get().updateProjectStatus(id, "planning");
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  stopProject: async (id) => {
    set({ error: null });
    try {
      await api.stopProject(id);
      get().updateProjectStatus(id, "paused");
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  approveProject: async (id, feedback) => {
    set({ error: null, humanRequired: false, humanReason: null });
    try {
      await api.approveProject(id, feedback);
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  fetchChatHistory: async (projectId) => {
    try {
      const messages = await api.getChatHistory(projectId);
      set({ chatMessages: messages });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  fetchPlan: async (projectId) => {
    try {
      const { plan_md } = await api.getProjectPlan(projectId);
      set({ planMd: plan_md });
    } catch (e: any) {
      set({ error: e.message });
    }
  },

  updatePlan: async (projectId, planMd) => {
    try {
      await api.updateProjectPlan(projectId, planMd);
      set({ planMd });
    } catch (e: any) {
      set({ error: e.message });
    }
  },
}));
