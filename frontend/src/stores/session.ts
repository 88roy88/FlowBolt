import { create } from 'zustand';
import type { Project } from '../types';
import * as api from '../services/api';

interface SessionState {
  currentProject: Project | null;
  projects: Project[];
  sessionId: string | null;
  setCurrentProject: (project: Project) => void;
  loadProjects: () => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentProject: null,
  projects: [],
  sessionId: null,

  setCurrentProject(project: Project) {
    set({ currentProject: project, sessionId: project.session_id });
  },

  async loadProjects() {
    const projects = await api.fetchProjects();
    set({ projects });
  },

  async createProject(name: string) {
    const project = await api.createProject(name);
    const projects = [...get().projects, project];
    set({ projects, currentProject: project, sessionId: project.session_id });
  },

  async deleteProject(id: string) {
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
