import { create } from 'zustand';
import type { Project } from '../types';
import * as api from '../services/api';
import { closeChatSocket } from '../services/websocket';
import { useChatStore } from './chat';
import { clearProjectCaches } from '../utils/projectCache';

interface SessionState {
  currentProject: Project | null;
  projects: Project[];
  projectId: string | null;
  isCreating: boolean;
  setCurrentProject: (project: Project) => void;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  renameProject: (id: string, name: string) => Promise<void>;
  updateProjectSummary: (projectId: string, summary: string) => void;
  setProjectPublishedUrl: (projectId: string, url: string) => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentProject: null,
  projects: [],
  projectId: null,
  isCreating: false,

  setCurrentProject(project: Project) {
    set({ currentProject: project, projectId: project.id });
    // Restore the selected model for this project
    if (project.selected_model) {
      useChatStore.setState({ selectedModel: project.selected_model });
    }
    useChatStore.getState().clearDataSources();
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
      const projects = [project, ...get().projects.filter((p) => p.id !== project.id)];
      set({ projects, currentProject: project, projectId: project.id });
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
    if (projects.length === 0) clearProjectCaches();
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

  setProjectPublishedUrl(projectId: string, url: string) {
    set((state) => {
      const projects = state.projects.map((p) =>
        p.id === projectId ? { ...p, published_url: url } : p
      );
      const currentProject = state.currentProject?.id === projectId
        ? { ...state.currentProject, published_url: url }
        : state.currentProject;
      return { projects, currentProject };
    });
  },
}));
