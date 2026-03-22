import { create } from 'zustand';
import type { Project } from '../types';
import * as api from '../services/api';
import { closeChatSocket } from '../services/websocket';
import { useChatStore } from './chat';

interface SessionState {
  currentProject: Project | null;
  projects: Project[];
  sessionId: string | null;
  isCreating: boolean;
  setCurrentProject: (project: Project) => void;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  renameProject: (id: string, name: string) => Promise<void>;
  updateProjectSummary: (projectId: string, summary: string) => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentProject: null,
  projects: [],
  sessionId: null,
  isCreating: false,

  setCurrentProject(project: Project) {
    set({ currentProject: project, sessionId: project.session_id });
    // Restore the selected model for this project
    if (project.selected_model) {
      useChatStore.setState({ selectedModel: project.selected_model });
    }
    useChatStore.getState().clearCases();
  },

  async loadProjects() {
    const projects = await api.fetchProjects();
    // Newest first
    projects.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    set({ projects });
  },

  async createProject(name: string) {
    set({ isCreating: true });
    try {
      const project = await api.createProject(name);
      const projects = [project, ...get().projects];
      set({ projects, currentProject: project, sessionId: project.session_id });
    } finally {
      set({ isCreating: false });
    }
  },

  async deleteProject(id: string) {
    const projectToDelete = get().projects.find((p) => p.id === id);
    if (projectToDelete?.session_id) {
      closeChatSocket(projectToDelete.session_id);
    }
    await api.deleteProject(id);
    const projects = get().projects.filter((p) => p.id !== id);
    const current = get().currentProject;
    if (current?.id === id) {
      const next = projects[0] ?? null;
      set({
        projects,
        currentProject: next,
        sessionId: next?.session_id ?? null,
      });
    } else {
      set({ projects });
    }
  },

  async renameProject(id: string, name: string) {
    await api.renameProject(id, name);
    set((state) => {
      const projects = state.projects.map((p) => p.id === id ? { ...p, name } : p);
      const currentProject = state.currentProject?.id === id
        ? { ...state.currentProject, name }
        : state.currentProject;
      return { projects, currentProject };
    });
  },

  updateProjectSummary(projectId: string, summary: string) {
    set((state) => {
      const projects = state.projects.map((p) =>
        p.id === projectId ? { ...p, summary } : p
      );
      const currentProject = state.currentProject?.id === projectId
        ? { ...state.currentProject, summary }
        : state.currentProject;
      return { projects, currentProject };
    });
  },
}));
