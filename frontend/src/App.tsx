import { useEffect, useState, useCallback } from 'react';
import { useSessionStore } from './stores/session';
import { useChatStore } from './stores/chat';
import { useFilesStore } from './stores/files';
import { useErrorStore } from './stores/errors';
import { AppShell } from './components/layout/AppShell';
import { ErrorToast, useErrorCapture } from './components/errors/ErrorToast';
import * as api from './services/api';

function getSessionIdFromHash(): string | null {
  const match = window.location.hash.match(/^#\/project\/(.+)$/);
  return match ? match[1] : null;
}

export default function App() {
  const { projects, currentProject, setCurrentProject, loadProjects, createProject } = useSessionStore();
  const loadHistory = useChatStore((s) => s.loadHistory);
  const loadFileTree = useFilesStore((s) => s.loadFileTree);
  useErrorCapture();
  const [newProjectName, setNewProjectName] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [loading, setLoading] = useState(true);
  const [backendAvailable, setBackendAvailable] = useState(true);
  const [checkingBackend, setCheckingBackend] = useState(true);

  const selectProject = useCallback((project: typeof projects[number]) => {
    setCurrentProject(project);
    window.location.hash = `#/project/${project.session_id}`;
    loadHistory(project.session_id);
    loadFileTree();
  }, [setCurrentProject, loadHistory, loadFileTree]);

  // Initialize theme (dark/light) once on app load
  useEffect(() => {
    const stored = window.localStorage.getItem('theme');
    let theme: 'light' | 'dark';
    if (stored === 'light' || stored === 'dark') {
      theme = stored;
    } else {
      theme = window.matchMedia &&
        window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light'
        : 'dark';
    }
    document.documentElement.dataset.theme = theme;
  }, []);

  // Check backend availability on mount
  useEffect(() => {
    async function checkBackend() {
      setCheckingBackend(true);
      const isAvailable = await api.checkBackendHealth();
      setBackendAvailable(isAvailable);
      setCheckingBackend(false);

      if (!isAvailable) {
        useErrorStore.getState().pushError({
          source: 'connection',
          message: 'Cannot connect to backend server. Please ensure the server is running.',
        });
      }
    }
    checkBackend();
  }, []);

  useEffect(() => {
    loadProjects()
      .catch((error) => {
        console.error('Failed to load projects:', error);
        // Show connection error to user
        useErrorStore.getState().pushError({
          source: 'connection',
          message: 'Failed to connect to backend server. Please ensure the server is running.',
        });
      })
      .finally(() => setLoading(false));
  }, [loadProjects]);

  // On load: match URL hash to a project, or auto-select first
  useEffect(() => {
    if (loading || projects.length === 0) {
      if (!loading && projects.length === 0) {
        setShowNewProject(true);
      }
      return;
    }
    if (currentProject) return;

    const hashSessionId = getSessionIdFromHash();
    const match = hashSessionId
      ? projects.find((p) => p.session_id === hashSessionId)
      : null;
    const target = match ?? projects[0];
    selectProject(target);
  }, [loading, projects, currentProject, selectProject]);

  // Listen for hash changes (back/forward)
  useEffect(() => {
    function onHashChange() {
      const hashSessionId = getSessionIdFromHash();
      if (!hashSessionId) return;
      const match = projects.find((p) => p.session_id === hashSessionId);
      if (match && match.id !== currentProject?.id) {
        selectProject(match);
      }
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [projects, currentProject, selectProject]);

  const handleCreate = async () => {
    const name = newProjectName.trim() || 'My Project';
    await createProject(name);
    setNewProjectName('');
    setShowNewProject(false);
    // After creation, the session store already has the new project selected.
    // Set the hash URL and start polling for files (scaffold takes a few seconds).
    const session = useSessionStore.getState();
    if (session.currentProject) {
      window.location.hash = `#/project/${session.currentProject.session_id}`;
      loadHistory(session.currentProject.session_id);
      // Poll for file tree until scaffold completes
      pollFileTree();
    }
  };

  function pollFileTree() {
    let attempts = 0;
    const maxAttempts = 15;
    const interval = setInterval(async () => {
      attempts++;
      await loadFileTree();
      const tree = useFilesStore.getState().fileTree;
      if (tree.length > 0 || attempts >= maxAttempts) {
        clearInterval(interval);
      }
    }, 2000);
  }

  if (loading || checkingBackend) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <p style={{ color: 'var(--text-dim)' }}>Loading...</p>
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
        <h1 style={{ color: 'var(--accent)', fontSize: '24px' }}>AI Builder</h1>
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
                Backend Server Unavailable
              </p>
              <p style={{ color: 'var(--text-dim)', fontSize: '14px' }}>
                Cannot connect to the backend server. Please ensure the server is running and try refreshing the page.
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
              Retry Connection
            </button>
          </>
        ) : (
          <>
            <p style={{ color: 'var(--text-dim)' }}>Create your first project to get started</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                placeholder="Project name"
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
                Create
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
