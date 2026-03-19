import { useState } from 'react';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, Trash2, FolderKanban, PanelLeftClose, Info, Loader2 } from 'lucide-react';
import { FlowBrand } from '../ui/flow-logo';
import type { ProjectSummary } from '../../types';
import { SummaryModal } from './SummaryModal';
import { pollFileTree } from '../../utils/pollFileTree';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

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
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowInput(false);
    await createProject(name);
    clearMessages();
    const session = useSessionStore.getState();
    if (session.currentProject) {
      window.location.hash = `#/project/${session.currentProject.session_id}`;
      loadHistory(session.currentProject.session_id);
      pollFileTree();
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
    if (pendingDeleteId !== id) {
      setPendingDeleteId(id);
      setTimeout(() => setPendingDeleteId(null), 3000);
      return;
    }
    setPendingDeleteId(null);
    const wasSelected = currentProject?.id === id;
    await deleteProject(id);
    if (wasSelected) {
      const next = useSessionStore.getState().currentProject;
      if (next) {
        window.location.hash = `#/project/${next.session_id}`;
        resetFiles();
        loadFileTree();
        clearMessages();
        loadHistory(next.session_id);
      } else {
        window.location.hash = '';
        resetFiles();
        clearMessages();
      }
    }
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
    <div className="flex flex-col h-full p-3">
      {/* Header with Flow44 branding */}
      <div className="flex items-center justify-between mb-3">
        <FlowBrand size="sm" />
        <div className="flex items-center gap-1">
          {onCloseSidebar && (
            <Button variant="ghost" size="icon-sm" onClick={onCloseSidebar} title="Hide projects panel">
              <PanelLeftClose size={16} />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => setShowInput(true)}
            disabled={isCreating}
            title="New Project"
          >
            <Plus size={18} />
          </Button>
        </div>
      </div>

      {/* New project input */}
      {showInput && (
        <div className="flex gap-1 mb-2">
          <Input
            autoFocus
            placeholder="Project name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCreate();
              if (e.key === 'Escape') setShowInput(false);
            }}
          />
          <Button size="sm" onClick={handleCreate}>Add</Button>
        </div>
      )}

      {/* Creating indicator */}
      {isCreating && (
        <div className="flex items-center gap-2 px-2 py-2.5 mb-2 rounded-md bg-background border border-border text-[13px] text-muted-foreground">
          <Loader2 size={14} className="shrink-0 animate-spin" />
          Scaffolding project...
        </div>
      )}

      {/* Project list */}
      <div className="flex-1 overflow-auto">
        {projects.map((project) => {
          const isActive = currentProject?.id === project.id;
          return (
            <div
              key={project.id}
              onClick={() => handleSelect(project)}
              className={`group flex items-center gap-2 p-2 cursor-pointer mb-0.5 transition-colors duration-100 rounded-r-md ${
                isActive
                  ? 'bg-background border-l-2 border-primary'
                  : 'hover:bg-muted/50 border-l-2 border-transparent'
              }`}
            >
              <FolderKanban size={16} className="text-primary shrink-0" />
              <span className="flex-1 text-[13px] truncate">{project.name}</span>
              {project.summary && (
                <Button variant="ghost" size="icon-sm" onClick={(e) => handleShowSummary(e, project)} title="View project summary" className="opacity-50 hover:opacity-100">
                  <Info size={14} />
                </Button>
              )}
              {pendingDeleteId === project.id ? (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={(e) => handleDelete(e, project.id)}
                  className="text-xs h-6 px-2"
                >
                  Delete?
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={(e) => handleDelete(e, project.id)}
                  title="Delete project"
                  className="opacity-0 group-hover:opacity-50 hover:!opacity-100"
                >
                  <Trash2 size={14} />
                </Button>
              )}
            </div>
          );
        })}
      </div>

      {summaryModal && (
        <SummaryModal
          projectName={summaryModal.projectName}
          summary={summaryModal.summary}
          onClose={() => setSummaryModal(null)}
        />
      )}
    </div>
  );
}
