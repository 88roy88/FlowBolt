import { useState } from 'react';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, Trash2, FolderKanban, PanelLeftClose, Info, X, Sparkles, FileText, Package } from 'lucide-react';
import type { ProjectSummary } from '../../types';

type SidebarProps = {
  onCloseSidebar?: () => void;
};

export function Sidebar({ onCloseSidebar }: SidebarProps) {
  const { projects, currentProject, setCurrentProject, createProject, deleteProject, isCreating } = useSessionStore();
  const { clearMessages, loadHistory } = useChatStore();
  const { loadFileTree, reset: resetFiles } = useFilesStore();
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);
  const [summaryModal, setSummaryModal] = useState<{ projectName: string; summary: ProjectSummary } | null>(null);

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowInput(false);
    await createProject(name);
    clearMessages();
    // Update URL hash and load data for the new project
    const session = useSessionStore.getState();
    if (session.currentProject) {
      window.location.hash = `#/project/${session.currentProject.session_id}`;
      loadHistory(session.currentProject.session_id);
      // Poll for scaffold to finish
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        await loadFileTree();
        const tree = useFilesStore.getState().fileTree;
        if (tree.length > 0 || attempts >= 15) {
          clearInterval(interval);
        }
      }, 2000);
    }
  };

  const handleSelect = (project: typeof projects[number]) => {
    setCurrentProject(project);
    window.location.hash = `#/project/${project.session_id}`;
    resetFiles();
    loadFileTree();
    loadHistory(project.session_id);
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await deleteProject(id);
  };

  const handleShowSummary = (e: React.MouseEvent, project: typeof projects[number]) => {
    e.stopPropagation();
    if (!project.summary) return;

    try {
      const parsedSummary = JSON.parse(project.summary) as ProjectSummary;
      setSummaryModal({ projectName: project.name, summary: parsedSummary });
    } catch (err) {
      console.error('Failed to parse project summary:', err);
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      padding: '12px',
    }}>
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
            {project.summary && (
              <button
                onClick={(e) => handleShowSummary(e, project)}
                style={{
                  padding: '2px',
                  color: 'var(--text-dim)',
                  opacity: 0.5,
                  borderRadius: '4px',
                }}
                title="View project summary"
              >
                <Info size={14} />
              </button>
            )}
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

      {/* Summary Modal */}
      {summaryModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
          }}
          onClick={() => setSummaryModal(null)}
        >
          <div
            style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '12px',
              padding: '20px',
              maxWidth: '500px',
              maxHeight: '80vh',
              overflow: 'auto',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setSummaryModal(null)}
              style={{
                position: 'absolute',
                top: '12px',
                right: '12px',
                padding: '4px',
                color: 'var(--text-dim)',
                borderRadius: '4px',
              }}
              title="Close"
            >
              <X size={18} />
            </button>

            <h3 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 600, paddingRight: '24px' }}>
              {summaryModal.projectName}
            </h3>

            <p style={{ marginBottom: '16px', lineHeight: '1.6', color: 'var(--text)' }}>
              {summaryModal.summary.summary}
            </p>

            {summaryModal.summary.tech_stack && summaryModal.summary.tech_stack.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '8px' }}>
                  Tech Stack
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {summaryModal.summary.tech_stack.map((tech, i) => (
                    <span
                      key={i}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        padding: '4px 10px',
                        background: 'var(--bg)',
                        border: '1px solid var(--border)',
                        borderRadius: '6px',
                        fontSize: '12px',
                        color: 'var(--accent)',
                      }}
                    >
                      <Package size={12} />
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {summaryModal.summary.features && summaryModal.summary.features.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '8px' }}>
                  Features
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {summaryModal.summary.features.map((feature, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <Sparkles size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
                      <span style={{ fontSize: '13px', lineHeight: '1.5' }}>{feature}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {summaryModal.summary.file_overview && Object.keys(summaryModal.summary.file_overview).length > 0 && (
              <div>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '8px' }}>
                  Key Files
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {Object.entries(summaryModal.summary.file_overview).map(([file, description]) => (
                    <div key={file} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px' }}>
                      <FileText size={13} style={{ color: 'var(--text-dim)', flexShrink: 0, marginTop: '2px' }} />
                      <span>
                        <strong style={{ color: 'var(--text)' }}>{file}</strong>
                        <span style={{ color: 'var(--text-dim)' }}> — {description}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
