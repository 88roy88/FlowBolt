import { useEffect, useState } from 'react';
import { useSessionStore } from './stores/session';
import { AppShell } from './components/layout/AppShell';

export default function App() {
  const { projects, loadProjects, createProject } = useSessionStore();
  const [newProjectName, setNewProjectName] = useState('');
  const [showNewProject, setShowNewProject] = useState(false);
  const [loading, setLoading] = useState(true);

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

  useEffect(() => {
    loadProjects()
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [loadProjects]);

  useEffect(() => {
    if (!loading && projects.length === 0) {
      setShowNewProject(true);
    }
  }, [loading, projects.length]);

  const handleCreate = async () => {
    const name = newProjectName.trim() || 'My Project';
    await createProject(name);
    setNewProjectName('');
    setShowNewProject(false);
  };

  if (loading) {
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
      </div>
    );
  }

  return <AppShell />;
}
