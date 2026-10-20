import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import './i18n';
import { useSessionStore } from './stores/session';
import { useChatStore } from './stores/chat';
import { useFilesStore } from './stores/files';
import { useErrorStore } from './stores/errors';
import { AppShell } from './components/layout/AppShell';
import { ErrorToast } from './components/errors/ErrorToast';
import { UnsavedEditsDialog } from './components/version/UnsavedEditsDialog';
import { useErrorCapture } from './hooks/useErrorCapture';
import { Loader2 } from 'lucide-react';
import { FlowBrand } from './components/ui/flow-logo';
import * as api from './services/api';
import { logger } from './services/logger';

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
      theme = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    document.documentElement.dataset.theme = theme;
  } catch {}
}

// Run immediately
initializeTheme();

export default function App() {
  const { t } = useTranslation();
  const { projects, currentProject, setCurrentProject, goHome, loadProjects, loadUserStatus, userStatus } = useSessionStore();
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadFileTree = useFilesStore((s) => s.loadFileTree);
  const resetFiles = useFilesStore((s) => s.reset);
  useErrorCapture();
  const [showNewProject, setShowNewProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState(true);
  const [checkingBackend, setCheckingBackend] = useState(true);
  const hasCache = hasProjectsCache();

  const selectProject = useCallback(
    (
      project: typeof projects[number],
      source: 'auto_select' | 'direct_link' | 'project_list' = 'auto_select',
      { replaceUrl = false } = {}
    ) => {
      setCurrentProject(project);
      if (replaceUrl) history.replaceState(null, '', `#/project/${project.id}`);
      else window.location.hash = `#/project/${project.id}`;
      resetFiles();
      loadHistory(project.id);
      loadFileTree();
      logger.info('project_opened', { entry_point: source });
    },
    [setCurrentProject, resetFiles, loadHistory, loadFileTree]
  );

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
    Promise.all([loadProjects(), loadUserStatus()])
      .then(() => {
        const hasProjects = useSessionStore.getState().projects.length > 0;
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
  }, [loadProjects, loadUserStatus, t]);

  // On load: match URL hash to a project, or auto-select first (admins, who see every project, stay on the home page)
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
    if (match) {
      selectProject(match, 'direct_link');
    } else if (!userStatus?.is_admin) {
      // Replace rather than push, so Back leaves the app instead of returning to an empty home page
      selectProject(projects[0], 'auto_select', { replaceUrl: true });
    }
  }, [loading, projects, currentProject, selectProject, userStatus]);

  // Listen for hash changes (back/forward)
  useEffect(() => {
    function onHashChange() {
      const hashProjectId = getProjectIdFromHash();
      if (!hashProjectId) {
        if (currentProject) {
          goHome();
          resetFiles();
        }
        return;
      }
      const match = projects.find((p) => p.id === hashProjectId);
      if (match && match.id !== currentProject?.id) {
        selectProject(match, 'direct_link');
      }
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [projects, currentProject, selectProject, goHome, resetFiles]);

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

  // Only show loading screen if no cache exists
  if ((loading || checkingBackend) && !hasCache) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 select-none">
        <FlowBrand size="lg" />
        <Loader2 size={20} className="animate-spin text-brand" />
      </div>
    );
  }

  // With no projects, users who can create one get the home page (AppShell); this screen covers everyone else
  const canCreate = userStatus?.is_platform_user || userStatus?.is_admin;
  if (showNewProject && projects.length === 0 && (!backendAvailable || !canCreate)) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-6 px-8 relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute top-[25%] start-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--primary)_8%,transparent),transparent_70%)] pointer-events-none" />

        <div className="relative z-10 flex flex-col items-center gap-6 w-full max-w-md">
          {/* Logo with glow */}
          <div className="relative">
            <div className="absolute inset-0 blur-3xl bg-[color-mix(in_srgb,var(--primary)_25%,transparent)] scale-[2] pointer-events-none" />
            <div className="relative drop-shadow-[0_0_20px_color-mix(in_srgb,var(--primary)_30%,transparent)]">
              <FlowBrand size="lg" />
            </div>
          </div>

          {!backendAvailable ? (
            <>
              <div className="w-full px-5 py-4 bg-surface rounded-xl border-2 border-destructive/50 text-center shadow-[0_0_20px_color-mix(in_srgb,var(--destructive)_10%,transparent)]">
                <p className="text-destructive font-semibold mb-1.5">{t('app.backendUnavailable')}</p>
                <p className="text-sm text-muted-foreground">{t('app.cannotConnect')}</p>
              </div>
              <button
                onClick={() => window.location.reload()}
                className="px-5 py-2 bg-primary text-text-on-accent rounded-lg font-semibold text-sm hover:opacity-90 transition-opacity shadow-[0_0_16px_color-mix(in_srgb,var(--primary)_30%,transparent)]"
              >
                {t('app.retryConnection')}
              </button>
            </>
          ) : (
            <div className="w-full px-5 py-4 bg-surface rounded-xl border border-border text-center">
              <p className="text-muted-foreground text-sm leading-relaxed">
                {t('app.noAccessMessage', "You don't have access to create projects yet. Ask your administrator for an invitation.")}
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <AppShell />
      <ErrorToast />
      <UnsavedEditsDialog />
    </>
  );
}
