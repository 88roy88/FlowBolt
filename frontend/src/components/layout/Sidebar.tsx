import { useState } from 'react';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, Trash2, FolderKanban } from 'lucide-react';

export function Sidebar() {
  const { projects, currentProject, setCurrentProject, createProject, deleteProject } = useSessionStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const loadFileTree = useFilesStore((s) => s.loadFileTree);
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    await createProject(name);
    clearMessages();
    setNewName('');
    setShowInput(false);
  };

  const handleSelect = (project: typeof projects[number]) => {
    setCurrentProject(project);
    clearMessages();
    loadFileTree();
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteProject(id);
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      padding: '12px',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '12px',
      }}>
        <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--accent)' }}>
          AI Builder
        </span>
        <button
          onClick={() => setShowInput(true)}
          style={{ padding: '4px', borderRadius: '4px', color: 'var(--text-dim)' }}
          title="New Project"
        >
          <Plus size={18} />
        </button>
      </div>

      {/* New project input */}
      {showInput && (
        <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
          <input
            autoFocus
            type="text"
            placeholder="Project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreate();
              if (e.key === 'Escape') setShowInput(false);
            }}
            style={{
              flex: 1,
              padding: '6px 8px',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: '4px',
              fontSize: '13px',
            }}
          />
          <button
            onClick={handleCreate}
            style={{
              padding: '6px 10px',
              background: 'var(--accent)',
              color: 'var(--bg)',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            Add
          </button>
        </div>
      )}

      {/* Project list */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {projects.map((project) => (
          <div
            key={project.id}
            onClick={() => handleSelect(project)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px',
              borderRadius: '6px',
              cursor: 'pointer',
              background: currentProject?.id === project.id ? 'var(--bg)' : 'transparent',
              marginBottom: '2px',
            }}
          >
            <FolderKanban size={16} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <span style={{
              flex: 1,
              fontSize: '13px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {project.name}
            </span>
            <button
              onClick={(e) => handleDelete(e, project.id)}
              style={{
                padding: '2px',
                color: 'var(--text-dim)',
                opacity: 0.5,
                borderRadius: '4px',
              }}
              title="Delete project"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
