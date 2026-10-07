import { create } from 'zustand';
import type { Project, UserStatus } from '../types';
import * as api from '../services/api';
import { closeChatSocket } from '../services/websocket';
import { useChatStore } from './chat';

type ProjectSearch = { query: string; results: Project[]; cursor: string | null };

interface SessionState {
  currentProject: Project | null;
  projects: Project[];
  projectsCursor: string | null;
  projectSearch: ProjectSearch | null;
  isLoadingMoreProjects: boolean;
  projectId: string | null;
  isCreating: boolean;
  userStatus: UserStatus | null;
  setCurrentProject: (project: Project) => void;
  loadUserStatus: () => Promise<void>;
  loadProjects: () => Promise<void>;
  loadMoreProjects: () => Promise<void>;
  searchProjects: (query: string) => Promise<void>;
  createProject: (name: string) => Promise<void>;
  deleteProject: (id: string) => Promise<void>;
  renameProject: (id: string, name: string) => Promise<void>;
  updateProjectSummary: (projectId: string, summary: string) => void;
  setProjectPublishedUrl: (projectId: string, handle: string) => void;
}

let latestSearchQuery = '';

function appendPage(existing: Project[], page: Project[]): Project[] {
  const seen = new Set(existing.map((p) => p.id));
  return [...existing, ...page.filter((p) => !seen.has(p.id))];
}

function patchProject(state: SessionState, projectId: string, patch: Partial<Project>): Partial<SessionState> {
  const apply = (list: Project[]) => list.map((p) => (p.id === projectId ? { ...p, ...patch } : p));
  return {
    projects: apply(state.projects),
    projectSearch: state.projectSearch && { ...state.projectSearch, results: apply(state.projectSearch.results) },
    currentProject: state.currentProject?.id === projectId ? { ...state.currentProject, ...patch } : state.currentProject,
  };
}

export const useSessionStore = create<SessionState>((set, get) => ({
  currentProject: null,
  projects: [],
  projectsCursor: null,
  projectSearch: null,
  isLoadingMoreProjects: false,
  projectId: null,
  isCreating: false,
  userStatus: null,

  setCurrentProject(project: Project) {
    set({ currentProject: project, projectId: project.id });
    if (project.selected_model) {
      useChatStore.setState({ selectedModel: project.selected_model });
    }
    useChatStore.getState().clearDataSources();
  },

  async loadUserStatus() {
    const userStatus = await api.fetchMe();
    set({ userStatus });
  },

  async loadProjects() {
    const page = await api.fetchProjects();
    set({ projects: page.projects, projectsCursor: page.next_cursor });
  },

  async loadMoreProjects() {
    const { projectSearch, projectsCursor, isLoadingMoreProjects } = get();
    const cursor = projectSearch ? projectSearch.cursor : projectsCursor;
    if (!cursor || isLoadingMoreProjects) return;

    set({ isLoadingMoreProjects: true });
    try {
      const page = await api.fetchProjects({ query: projectSearch?.query, cursor });
      set((state) => {
        if (!projectSearch) {
          return { projects: appendPage(state.projects, page.projects), projectsCursor: page.next_cursor };
        }
        if (state.projectSearch?.query !== projectSearch.query) return {};
        return {
          projectSearch: {
            ...state.projectSearch,
            results: appendPage(state.projectSearch.results, page.projects),
            cursor: page.next_cursor,
          },
        };
      });
    } finally {
      set({ isLoadingMoreProjects: false });
    }
  },

  async searchProjects(query: string) {
    latestSearchQuery = query;
    if (!query) {
      set({ projectSearch: null });
      return;
    }
    const page = await api.fetchProjects({ query });
    if (latestSearchQuery !== query) return;
    set({ projectSearch: { query, results: page.projects, cursor: page.next_cursor } });
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
    const prevProjects = get().projects;
    const prevCurrent = get().currentProject;
    const prevProjectId = get().projectId;

    const projectToDelete = prevProjects.find((p) => p.id === id);
    if (projectToDelete) {
      closeChatSocket(projectToDelete.id);
    }

    const prevSearch = get().projectSearch;

    // Optimistically update the UI before the network round-trip, rolling back on failure.
    const projects = prevProjects.filter((p) => p.id !== id);
    const projectSearch = prevSearch && { ...prevSearch, results: prevSearch.results.filter((p) => p.id !== id) };
    if (prevCurrent?.id === id) {
      const next = projects[0] ?? null;
      set({
        projects,
        projectSearch,
        currentProject: next,
        projectId: next?.id ?? null,
      });
    } else {
      set({ projects, projectSearch });
    }

    try {
      await api.deleteProject(id);
    } catch (e) {
      set({ projects: prevProjects, projectSearch: prevSearch, currentProject: prevCurrent, projectId: prevProjectId });
      throw e;
    }
  },

  async renameProject(id: string, name: string) {
    await api.renameProject(id, name);
    set((state) => patchProject(state, id, { name }));
  },

  updateProjectSummary(projectId: string, summary: string) {
    set((state) => patchProject(state, projectId, { summary }));
  },

  setProjectPublishedUrl(projectId: string, handle: string) {
    set((state) => patchProject(state, projectId, { published_url: handle }));
  },
}));
