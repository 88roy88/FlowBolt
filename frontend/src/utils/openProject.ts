import type { Project } from '../types';
import { useSessionStore } from '../stores/session';
import { useChatStore } from '../stores/chat';
import { useFilesStore } from '../stores/files';
import { pollFileTree } from './pollFileTree';
import { logger } from '../services/logger';

/** Switch the workspace to an existing project without a page reload. */
export function openProject(project: Project, entryPoint = 'project_list'): void {
  useSessionStore.getState().setCurrentProject(project);
  logger.info('project_opened', { entry_point: entryPoint });
  window.location.hash = `#/project/${project.id}`;
  useFilesStore.getState().reset();
  useFilesStore.getState().loadFileTree();
  useChatStore.getState().loadHistory(project.id);
}

/** Create a named project and open it. */
export async function createAndOpenProject(name: string): Promise<void> {
  await useSessionStore.getState().createProject(name);
  useChatStore.getState().clearMessages();
  const project = useSessionStore.getState().currentProject;
  if (project) {
    window.location.hash = `#/project/${project.id}`;
    useChatStore.getState().loadHistory(project.id);
    pollFileTree();
  }
}
