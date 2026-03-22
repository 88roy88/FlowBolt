import { useState, useRef, useEffect } from 'react';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, Pin, PinOff, Loader2, MoreHorizontal, Trash2, Info, Settings, Pencil } from 'lucide-react';
import { FlowBrand } from '../ui/flow-logo';
import type { ProjectSummary } from '../../types';
import { SummaryModal } from './SummaryModal';
import { pollFileTree } from '../../utils/pollFileTree';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

type SidebarProps = {
  onCloseSidebar?: () => void;
  isPinned?: boolean;
  onPin?: () => void;
  onOpenSettings?: () => void;
};

// Stable color per project based on name hash
const PROJECT_COLORS = [
  'bg-[#89b4fa]/20 text-[#89b4fa]',   // blue
  'bg-[#a6e3a1]/20 text-[#a6e3a1]',   // green
  'bg-[#f9e2af]/20 text-[#f9e2af]',   // yellow
  'bg-[#cba6f7]/20 text-[#cba6f7]',   // purple
  'bg-[#f38ba8]/20 text-[#f38ba8]',   // pink
  'bg-[#94e2d5]/20 text-[#94e2d5]',   // teal
  'bg-[#fab387]/20 text-[#fab387]',   // peach
  'bg-[#74c7ec]/20 text-[#74c7ec]',   // sky
];

function getProjectColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  return PROJECT_COLORS[Math.abs(hash) % PROJECT_COLORS.length];
}

function getInitials(name: string) {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function Sidebar({ onCloseSidebar, isPinned, onPin, onOpenSettings }: SidebarProps) {
  const { projects, currentProject, setCurrentProject, createProject, deleteProject, renameProject, isCreating } = useSessionStore();
  const { clearMessages, loadHistory } = useChatStore();
  const { loadFileTree, reset: resetFiles } = useFilesStore();
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);
  const [summaryModal, setSummaryModal] = useState<{ projectName: string; summary: ProjectSummary } | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpenId) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
        setPendingDeleteId(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpenId]);

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

  const handleDelete = async (id: string) => {
    if (pendingDeleteId !== id) {
      setPendingDeleteId(id);
      return;
    }
    setPendingDeleteId(null);
    setMenuOpenId(null);
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

  const startRename = (project: typeof projects[number]) => {
    setMenuOpenId(null);
    setRenamingId(project.id);
    setRenameValue(project.name);
  };

  const submitRename = async () => {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    await renameProject(renamingId, renameValue.trim());
    setRenamingId(null);
  };

  const handleShowSummary = (project: typeof projects[number]) => {
    setMenuOpenId(null);
    if (!project.summary) return;
    try {
      const parsedSummary = JSON.parse(project.summary) as ProjectSummary;
      setSummaryModal({ projectName: project.name, summary: parsedSummary });
    } catch (err) {
      console.error('Failed to parse project summary:', err);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3">
        <FlowBrand size="sm" />
        <div className="flex items-center gap-0.5">
          {onPin && !isPinned && (
            <Button variant="ghost" size="icon-sm" onClick={onPin} title="Pin sidebar open">
              <Pin size={14} />
            </Button>
          )}
          {isPinned && onCloseSidebar && (
            <Button variant="ghost" size="icon-sm" onClick={onCloseSidebar} title="Unpin sidebar">
              <PinOff size={14} />
            </Button>
          )}
        </div>
      </div>

      {/* New project button */}
      <div className="px-3 mb-2">
        {showInput ? (
          <div className="flex gap-1">
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
        ) : (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowInput(true)}
            disabled={isCreating}
            className="w-full justify-start gap-2"
          >
            <Plus size={14} />
            New Project
          </Button>
        )}
      </div>

      {/* Creating indicator */}
      {isCreating && (
        <div className="flex items-center gap-2 mx-3 px-2 py-2.5 mb-2 rounded-md bg-background border border-border text-[13px] text-muted-foreground">
          <Loader2 size={14} className="shrink-0 animate-spin" />
          Scaffolding project...
        </div>
      )}

      {/* Project list */}
      <div className="flex-1 overflow-auto px-2">
        {projects.map((project) => {
          const isActive = currentProject?.id === project.id;
          const isMenuOpen = menuOpenId === project.id;
          const colorClass = getProjectColor(project.name);
          return (
            <div key={project.id} className="relative">
              <div
                onClick={() => handleSelect(project)}
                data-testid={`project-item-${project.id}`}
                className={`group flex items-center gap-2.5 px-2 py-1.5 cursor-pointer mb-0.5 transition-colors duration-100 rounded-md ${
                  isActive ? 'bg-muted/60' : 'hover:bg-muted/30'
                }`}
              >
                <div className={`w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold shrink-0 ${colorClass}`}>
                  {getInitials(project.name)}
                </div>
                {renamingId === project.id ? (
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') submitRename();
                      if (e.key === 'Escape') setRenamingId(null);
                    }}
                    onBlur={submitRename}
                    onClick={(e) => e.stopPropagation()}
                    className="flex-1 text-[13px] bg-background border border-border rounded px-1.5 py-0.5"
                  />
                ) : (
                  <span className="flex-1 text-[13px] truncate">{project.name}</span>
                )}
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setMenuOpenId(isMenuOpen ? null : project.id);
                    setPendingDeleteId(null);
                  }}
                  className="opacity-0 group-hover:opacity-40 hover:!opacity-100 shrink-0"
                >
                  <MoreHorizontal size={14} />
                </Button>
              </div>

              {isMenuOpen && (
                <div
                  ref={menuRef}
                  className="absolute right-2 top-full z-50 mt-0.5 min-w-[140px] bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] py-1 animate-card-in"
                >
                  <button
                    onClick={() => startRename(project)}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
                  >
                    <Pencil size={13} className="text-muted-foreground" />
                    Rename
                  </button>
                  {project.summary && (
                    <button
                      onClick={() => handleShowSummary(project)}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
                    >
                      <Info size={13} className="text-muted-foreground" />
                      Summary
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(project.id)}
                    className={`w-full flex items-center gap-2 px-3 py-1.5 text-[13px] transition-colors text-left ${
                      pendingDeleteId === project.id
                        ? 'text-destructive bg-destructive/10'
                        : 'text-foreground hover:bg-muted/50'
                    }`}
                  >
                    <Trash2 size={13} className={pendingDeleteId === project.id ? 'text-destructive' : 'text-muted-foreground'} />
                    {pendingDeleteId === project.id ? 'Confirm delete?' : 'Delete'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Bottom: Settings */}
      <div className="border-t border-border px-3 py-2">
        <Button variant="ghost" size="sm" onClick={onOpenSettings} className="w-full justify-start gap-2 text-muted-foreground">
          <Settings size={14} />
          <span className="text-[13px]">Settings</span>
        </Button>
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
