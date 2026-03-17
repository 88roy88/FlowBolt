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
  },

  async loadProjects() {
    const projects = await api.fetchProjects();
    set({ projects });
  },

  async createProject(name: string) {
    set({ isCreating: true });
    try {
      const project = await api.createProject(name);
      const projects = [...get().projects, project];
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
}));
