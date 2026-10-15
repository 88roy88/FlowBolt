import i18n from '../i18n';
import { useSessionStore } from '../stores/session';
import { useChatStore } from '../stores/chat';
import { useFilesStore } from '../stores/files';
import { useErrorStore } from '../stores/errors';
import { pollFileTree } from './pollFileTree';

/** Home-page entry point: create an untitled project, open it, and send the first prompt into it. */
export async function startProjectFromPrompt(message: string): Promise<void> {
  try {
    await useSessionStore.getState().createProject(i18n.t('sidebar.untitledProject'));
  } catch (err) {
    console.error('Failed to create project:', err);
    useErrorStore.getState().pushError({
      source: 'connection',
      message: i18n.t('sidebar.createProjectError'),
    });
    return;
  }

  try { localStorage.setItem('has-projects', 'true'); } catch {}
  const project = useSessionStore.getState().currentProject;
  if (!project) return;

  window.location.hash = `#/project/${project.id}`;
  useFilesStore.getState().reset();
  await useChatStore.getState().loadHistory(project.id);
  pollFileTree();
  useChatStore.getState().sendMessage(message);
}
