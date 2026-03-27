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
import { authSession, PopupBlockedError } from './auth/authSession';

function getProjectIdFromHash(): string | null {
  const match = window.location.hash.match(/^#\/project\/(.+)$/);
  return match ? match[1] : null;
}

function hasProjectsCache(): boolean {
  try {
    const cache = localStorage.getItem('has-projects');
    return cache === 'true';
  } catch {
    return false;
  }
}

function setHasProjectsCache(hasProjects: boolean) {
  try {
    localStorage.setItem('has-projects', hasProjects ? 'true' : 'false');
  } catch {}
}

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
  const { projects, currentProject, setCurrentProject, loadProjects, createProject } = useSessionStore();
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadFileTree = useFilesStore((s) => s.loadFileTree);
  const resetFiles = useFilesStore((s) => s.reset);
  useErrorCapture();
  const [newProjectName, setNewProjectName] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState(true);
  const [checkingBackend, setCheckingBackend] = useState(true);
  const [authPhase, setAuthPhase] = useState<'loading' | 'needs_sign_in' | 'ready' | 'config_error'>('loading');
  const [signInError, setSignInError] = useState<string | null>(null);
  const hasCache = hasProjectsCache();

  const selectProject = useCallback((project: typeof projects[number]) => {
    setCurrentProject(project);
    window.location.hash = `#/project/${project.id}`;
    resetFiles();
    loadHistory(project.id);
    loadFileTree();
  }, [setCurrentProject, resetFiles, loadHistory, loadFileTree]);

  useEffect(() => {
    let cancelled = false;
    authSession
      .ensureInitialSession()
      .then((result) => {
        if (cancelled) return;
        setAuthPhase(result === 'ready' ? 'ready' : 'needs_sign_in');
      })
      .catch((e) => {
        console.error('Authentication bootstrap failed:', e);
        if (!cancelled) setAuthPhase('config_error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Check backend availability on mount
  useEffect(() => {
    if (authPhase !== 'ready') return;
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
  }, [authPhase, t]);

  useEffect(() => {
    if (authPhase !== 'ready') return;
    loadProjects()
      .then(() => {
        const hasProjects = useSessionStore.getState().projects.length > 0;
        setHasProjectsCache(hasProjects);
      })
      .catch((error) => {
        console.error('Failed to load projects:', error);
        // Show connection error to user
        useErrorStore.getState().pushError({
          source: 'connection',
          message: t('errors.failedToConnect'),
        });
      })
      .finally(() => setLoading(false));
  }, [authPhase, loadProjects, t]);

  // On load: match URL hash to a project, or auto-select first
  useEffect(() => {
    if (loading || projects.length === 0) {
      if (!loading && projects.length === 0) {
        setShowNewProject(true);
        setHasProjectsCache(false); // Clear cache if no projects
      }
      return;
    }
    if (currentProject) return;

    const hashProjectId = getProjectIdFromHash();
    const match = hashProjectId
      ? projects.find((p) => p.id === hashProjectId)
      : null;
    const target = match ?? projects[0];
    selectProject(target);
  }, [loading, projects, currentProject, selectProject]);

  // Listen for hash changes (back/forward)
  useEffect(() => {
    function onHashChange() {
      const hashProjectId = getProjectIdFromHash();
      if (!hashProjectId) return;
      const match = projects.find((p) => p.id === hashProjectId);
      if (match && match.id !== currentProject?.id) {
        selectProject(match);
      }
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [projects, currentProject, selectProject]);

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

  if (authPhase === 'loading') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 select-none">
        <FlowBrand size="lg" />
        <Loader2 size={20} className="animate-spin text-[#2bbcc4]" />
        <p className="text-sm text-[var(--text-dim)]">{t('app.authenticating')}</p>
      </div>
    );
  }

  if (authPhase === 'needs_sign_in') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 select-none px-6 text-center max-w-lg mx-auto">
        <FlowBrand size="lg" />
        <p className="text-[var(--text-dim)]">{t('app.signInPrompt')}</p>
        {signInError ? (
          <p className="text-sm text-[var(--danger)]">{signInError}</p>
        ) : null}
        <button
          type="button"
          className="px-4 py-2 rounded-md font-semibold bg-[var(--accent)] text-[var(--bg)]"
          onClick={() => {
            setSignInError(null);
            authSession
              .signInInteractive()
              .then(() => setAuthPhase('ready'))
              .catch((e) => {
                console.error(e);
                setSignInError(
                  e instanceof PopupBlockedError ? t('app.popupBlockedHint') : t('app.authConfigurationError'),
                );
              });
          }}
        >
          {t('app.openSignIn')}
        </button>
      </div>
    );
  }

  if (authPhase === 'config_error') {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 select-none px-6 text-center">
        <FlowBrand size="lg" />
        <p className="text-[var(--text-dim)] max-w-md">{t('app.authConfigurationError')}</p>
        <button
          type="button"
          className="px-4 py-2 rounded-md font-semibold bg-[var(--accent)] text-[var(--bg)]"
          onClick={() => {
            setAuthPhase('loading');
            authSession
              .ensureInitialSession()
              .then((result) => {
                setAuthPhase(result === 'ready' ? 'ready' : 'needs_sign_in');
              })
              .catch((e) => {
                console.error(e);
                setAuthPhase('config_error');
              });
          }}
        >
          {t('app.retryAuth')}
        </button>
      </div>
    );
  }

  // Only show loading screen if no cache exists
  if ((loading || checkingBackend) && !hasCache) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 select-none">
        <FlowBrand size="lg" />
        <Loader2 size={20} className="animate-spin text-[#2bbcc4]" />
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
