import { useState } from 'react';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, Trash2, FolderKanban, PanelLeftClose } from 'lucide-react';

type SidebarProps = {
  onCloseSidebar?: () => void;
};

export function Sidebar({ onCloseSidebar }: SidebarProps) {
  const { projects, currentProject, setCurrentProject, createProject, deleteProject, isCreating } = useSessionStore();
  const { clearMessages, loadHistory } = useChatStore();
  const { loadFileTree, reset: resetFiles } = useFilesStore();
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowInput(false);
    await createProject(name);
    clearMessages();
  };

  const handleSelect = (project: typeof projects[number]) => {
    setCurrentProject(project);
    resetFiles();
    loadFileTree();
    loadHistory(project.session_id);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteProject(id);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '12px',
        background: 'var(--surface)',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px',
        }}
      >
        <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--accent)' }}>
          AI Builder
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          {onCloseSidebar && (
            <button
              type="button"
              onClick={onCloseSidebar}
              title="Hide projects panel"
              style={{
                padding: '4px',
                borderRadius: '4px',
                color: 'var(--text-dim)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              <PanelLeftClose size={16} />
            </button>
          )}
          <button
            onClick={() => setShowInput(true)}
            disabled={isCreating}
            style={{
              padding: '4px',
              borderRadius: '4px',
              color: 'var(--text-dim)',
              opacity: isCreating ? 0.4 : 1,
              background: 'transparent',
              border: 'none',
              cursor: isCreating ? 'default' : 'pointer',
            }}
            title="New Project"
          >
            <Plus size={18} />
          </button>
        </div>
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

      {/* Creating indicator */}
      {isCreating && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 8px',
          marginBottom: '8px',
          borderRadius: '6px',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          fontSize: '13px',
          color: 'var(--text-dim)',
        }}>
          <span style={{
            display: 'inline-block',
            width: '14px',
            height: '14px',
            border: '2px solid var(--border)',
            borderTopColor: 'var(--accent)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            flexShrink: 0,
          }} />
          Scaffolding project...
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
              background:
                currentProject?.id === project.id ? 'rgba(var(--accent-rgb), 0.14)' : 'transparent',
              borderLeft:
                currentProject?.id === project.id ? '2px solid var(--accent)' : '2px solid transparent',
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
