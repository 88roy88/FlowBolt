import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import './i18n';
import { useSessionStore } from './stores/session';
import { useChatStore } from './stores/chat';
import { useFilesStore } from './stores/files';
import { useErrorStore } from './stores/errors';
import { AppShell } from './components/layout/AppShell';
import { ErrorToast } from './components/errors/ErrorToast';
import { useErrorCapture } from './hooks/useErrorCapture';
import { pollFileTree } from './utils/pollFileTree';
import { Loader2 } from 'lucide-react';
import { FlowBrand } from './components/ui/flow-logo';
import * as api from './services/api';
import { getAppName } from './utils/easterEgg';
import { clearProjectCaches, hasProjectsCache, setHasProjectsCache } from './utils/projectCache';
import {
  getProjectIdFromHash,
  resolveRouteAction,
  goToAppHome,
} from './utils/projectRoute';

// Initialize theme before React renders to prevent flicker
function initializeTheme() {
  try {
    const stored = window.localStorage.getItem('theme');
    let theme: 'light' | 'dark';
    if (stored === 'light' || stored === 'dark') {
      theme = stored;
    } else {
      theme = window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.dataset.theme = theme;
  } catch {}
}

// Run immediately
initializeTheme();

export default function App() {
  const { t } = useTranslation();
  const { projects, setCurrentProject, loadProjects, createProject } = useSessionStore();
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadFileTree = useFilesStore((s) => s.loadFileTree);
  const resetFiles = useFilesStore((s) => s.reset);
  useErrorCapture();
  const [newProjectName, setNewProjectName] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState(true);
  const [checkingBackend, setCheckingBackend] = useState(true);
  const hasCache = hasProjectsCache();

  // Easter egg: update document title for special users
  useEffect(() => {
    document.title = getAppName();
  }, []);

  const selectProject = useCallback((project: typeof projects[number]) => {
    setCurrentProject(project);
    window.location.hash = `#/project/${project.id}`;
    resetFiles();
    loadHistory(project.id);
    loadFileTree();
  }, [setCurrentProject, resetFiles, loadHistory, loadFileTree]);

  useEffect(() => {
    async function checkBackend() {
      const isAvailable = await api.checkBackendHealth();
      setBackendAvailable(isAvailable);
      setCheckingBackend(false);

      if (!isAvailable) {
        useErrorStore.getState().pushError({
          source: 'connection',
          message: t('errors.failedToConnect'),
        });
      }
    }
    checkBackend();
  }, [t]);

  useEffect(() => {
    loadProjects()
      .then(() => {
        const loaded = useSessionStore.getState().projects;
        const hasProjects = loaded.length > 0;
        if (!hasProjects) clearProjectCaches();
        setHasProjectsCache(hasProjects);
      })
      .catch((error) => {
        console.error('Failed to load projects:', error);
        useErrorStore.getState().pushError({
          source: 'connection',
          message: t('errors.failedToConnect'),
        });
      })
      .finally(() => setLoading(false));
  }, [loadProjects, t]);

  const syncRouteFromUrl = useCallback(() => {
    const hashProjectId = getProjectIdFromHash();
    const { projects: loadedProjects, currentProject } = useSessionStore.getState();
    const action = resolveRouteAction({
      hashProjectId,
      projects: loadedProjects,
      loading,
      currentProjectId: currentProject?.id ?? null,
    });

    switch (action.type) {
      case 'redirect_home':
        goToAppHome();
        return;
      case 'show_empty_state':
        setShowNewProject(true);
        setHasProjectsCache(false);
        return;
      case 'select_project':
        setShowNewProject(false);
        selectProject(action.project);
        return;
      case 'none':
        if (!loading && loadedProjects.length > 0) {
          setShowNewProject(false);
        }
        return;
    }
  }, [loading, selectProject]);

  useEffect(() => {
    syncRouteFromUrl();
  }, [syncRouteFromUrl, projects]);

  useEffect(() => {
    function onHashChange() {
      syncRouteFromUrl();
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [syncRouteFromUrl]);

  // Auto-recover state when network comes back online
  useEffect(() => {
    function handleOnline() {
      const projectId = useSessionStore.getState().projectId;
      if (projectId) {
        loadHistory(projectId);
        loadFileTree();
      }
    }
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [loadHistory, loadFileTree]);

  const handleCreate = async () => {
    const name = newProjectName.trim() || 'My Project';
    await createProject(name);
    setNewProjectName('');
    setShowNewProject(false);
    setHasProjectsCache(true); // Update cache after creating project
    // After creation, the session store already has the new project selected.
    // Set the hash URL and start polling for files (scaffold takes a few seconds).
    const session = useSessionStore.getState();
    if (session.currentProject) {
      window.location.hash = `#/project/${session.currentProject.id}`;
      resetFiles();
      loadHistory(session.currentProject.id);
      pollFileTree();
    }
  };

  // Only show loading screen if no cache exists
  if ((loading || checkingBackend) && !hasCache) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 select-none">
        <FlowBrand size="lg" />
        <Loader2 size={20} className="animate-spin text-brand" />
      </div>
    );
  }

  if (showNewProject && projects.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        gap: '16px',
      }}>
        <FlowBrand size="lg" />
        {!backendAvailable ? (
          <>
            <div style={{
              padding: '16px 24px',
              background: 'var(--surface)',
              border: '2px solid var(--danger)',
              borderRadius: '8px',
              maxWidth: '500px',
              textAlign: 'center',
            }}>
              <p style={{ color: 'var(--danger)', fontWeight: 600, marginBottom: '8px' }}>
                {t('app.backendUnavailable')}
              </p>
              <p style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
                {t('app.cannotConnect')}
              </p>
            </div>
            <button
              onClick={() => window.location.reload()}
              style={{
                padding: '8px 16px',
                background: 'var(--accent)',
                color: 'var(--bg)',
                borderRadius: '6px',
                fontWeight: 600,
              }}
            >
              {t('app.retryConnection')}
            </button>
          </>
        ) : (
          <>
            <p style={{ color: 'var(--text-dim)' }}>{t('app.createFirstProject')}</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                placeholder={t('common.projectName')}
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleCreate(); }}
                style={{
                  padding: '8px 12px',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  width: '250px',
                }}
              />
              <button
                onClick={handleCreate}
                style={{
                  padding: '8px 16px',
                  background: 'var(--accent)',
                  color: 'var(--bg)',
                  borderRadius: '6px',
                  fontWeight: 600,
                }}
              >
                {t('common.create')}
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <>
      <AppShell />
      <ErrorToast />
    </>
  );
}
