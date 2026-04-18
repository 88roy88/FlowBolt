import { create } from "zustand";
import type { Project } from "../types";
import * as api from "../services/api";
import { closeChatSocket } from "../services/websocket";
import { useChatStore } from "./chat";

interface SessionState {
  currentProject: Project | null;
  projects: Project[];
  projectId: string | null;
  isCreating: boolean;
  pendingRenameProjectId: string | null;
  setCurrentProject: (project: Project) => void;
  goHome: () => void;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  renameProject: (id: string, name: string) => Promise<void>;
  updateProjectSummary: (projectId: string, summary: string) => void;
  setProjectPublishedUrl: (projectId: string, url: string) => void;
  setPendingRenameProjectId: (id: string | null) => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentProject: null,
  projects: [],
  projectId: null,
  isCreating: false,
  pendingRenameProjectId: null,

  setCurrentProject(project: Project) {
    set({ currentProject: project, projectId: project.id });
    // Restore the selected model for this project
    if (project.selected_model) {
      useChatStore.setState({ selectedModel: project.selected_model });
    }
    useChatStore.getState().clearDataSources();
  },

  goHome() {
    set({ currentProject: null, projectId: null });
    useChatStore.getState().clearMessages();
    window.location.hash = "";
  },

  async loadProjects() {
    const projects = await api.fetchProjects();
    // Newest first
    projects.sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
    set({ projects });
  },

  async createProject(name: string) {
    // Optimistic: immediately add a temp project so the UI transitions before the API responds
    const tempId = crypto.randomUUID();
    const tempProject: Project = {
      id: tempId,
      name,
      created_at: new Date().toISOString(),
    };
    set({
      projects: [tempProject, ...get().projects],
      currentProject: tempProject,
      projectId: tempId,
      isCreating: true,
    });
    window.location.hash = `#/project/${tempId}`;

    try {
      const project = await api.createProject(name);
      // Swap the temp entry with the real project
      set((state) => ({
        projects: state.projects.map((p) => (p.id === tempId ? project : p)),
        currentProject:
          state.currentProject?.id === tempId ? project : state.currentProject,
        projectId: state.projectId === tempId ? project.id : state.projectId,
      }));
      // Update URL hash from temp ID to real ID
      if (window.location.hash === `#/project/${tempId}`) {
        window.location.hash = `#/project/${project.id}`;
      }
    } catch {
      // Roll back the optimistic update on failure
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== tempId),
        currentProject:
          state.currentProject?.id === tempId ? null : state.currentProject,
        projectId: state.projectId === tempId ? null : state.projectId,
      }));
      if (window.location.hash === `#/project/${tempId}`) {
        window.location.hash = "";
      }
    } finally {
      set({ isCreating: false });
    }
  },

  async deleteProject(id: string) {
    const projectToDelete = get().projects.find((p) => p.id === id);
    if (projectToDelete) {
      closeChatSocket(projectToDelete.id);
    }
    await api.deleteProject(id);
    const projects = get().projects.filter((p) => p.id !== id);
    const current = get().currentProject;
    if (current?.id === id) {
      const next = projects[0] ?? null;
      set({
        projects,
        currentProject: next,
        projectId: next?.id ?? null,
      });
    } else {
      set({ projects });
    }
  },

  async renameProject(id: string, name: string) {
    await api.renameProject(id, name);
    set((state) => {
      const projects = state.projects.map((p) =>
        p.id === id ? { ...p, name } : p,
      );
      const currentProject =
        state.currentProject?.id === id
          ? { ...state.currentProject, name }
          : state.currentProject;
      return { projects, currentProject };
    });
  },

  updateProjectSummary(projectId: string, summary: string) {
    set((state) => {
      const projects = state.projects.map((p) =>
        p.id === projectId ? { ...p, summary } : p,
      );
      const currentProject =
        state.currentProject?.id === projectId
          ? { ...state.currentProject, summary }
          : state.currentProject;
      return { projects, currentProject };
    });
  },

  setPendingRenameProjectId(id: string | null) {
    set({ pendingRenameProjectId: id });
  },

  setProjectPublishedUrl(projectId: string, url: string) {
    set((state) => {
      const projects = state.projects.map((p) =>
        p.id === projectId ? { ...p, published_url: url } : p,
      );
      const currentProject =
        state.currentProject?.id === projectId
          ? { ...state.currentProject, published_url: url }
          : state.currentProject;
      return { projects, currentProject };
    });
  },
}));
