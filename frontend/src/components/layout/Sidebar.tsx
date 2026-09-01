import { useState, useRef, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Plus, PanelLeftClose, Loader2, MoreHorizontal, Trash2, Info, Settings, Pencil, Moon, Share2, Shield, Search } from 'lucide-react';
import { FlowBrand } from '../ui/flow-logo';
import { DELETE_ROLES, MANAGE_ROLES, type ProjectSummary } from '../../types';
import { SummaryModal } from './SummaryModal';
import { ShareModal } from '../sharing/ShareModal';
import { pollFileTree } from '../../utils/pollFileTree';
import { reapProject } from '../../services/api';
import { Button } from '../ui/button';
import { Input } from '../ui/input';

type SidebarProps = {
  onCollapse?: () => void;
  onOpenSettings?: () => void;
  onOpenAdmin?: () => void;
};

// Stable color per project based on name hash
const PROJECT_COLORS = [
  'bg-primary/20 text-primary',
  'bg-success/20 text-success',
  'bg-warning/20 text-warning',
  'bg-project-purple/20 text-project-purple',
  'bg-destructive/20 text-destructive',
  'bg-project-teal/20 text-project-teal',
  'bg-project-peach/20 text-project-peach',
  'bg-project-sky/20 text-project-sky',
];

function getProjectColor(name: string) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = ((hash << 5) - hash + name.charCodeAt(i)) | 0;
  return PROJECT_COLORS[Math.abs(hash) % PROJECT_COLORS.length];
}

const anchorName = (id: string) => `--a${id.replace(/-/g, '')}`;

function getInitials(name: string) {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function Sidebar({ onCollapse, onOpenSettings, onOpenAdmin }: SidebarProps) {
  const { t } = useTranslation();
  const { projects, currentProject, setCurrentProject, createProject, deleteProject, renameProject, isCreating, userStatus } = useSessionStore();
  const { clearMessages, loadHistory } = useChatStore();
  const { loadFileTree, reset: resetFiles } = useFilesStore();
  const [searchQuery, setSearchQuery] = useState('');
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);
  const [summaryModal, setSummaryModal] = useState<{ projectName: string; summary: ProjectSummary; } | null>(null);
  const [shareModal, setShareModal] = useState<{ projectId: string; projectName: string; ownerUserId?: string; } | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [menuProjectId, setMenuProjectId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const canCreate = userStatus?.is_platform_user || userStatus?.is_admin;

  const closeMenu = () => menuRef.current?.hidePopover();

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowInput(false);
    await createProject(name);
    clearMessages();
    const session = useSessionStore.getState();
    if (session.currentProject) {
      window.location.hash = `#/project/${session.currentProject.id}`;
      loadHistory(session.currentProject.id);
      pollFileTree();
    }
  };

  const handleSelect = (project: typeof projects[number]) => {
    setCurrentProject(project);
    window.location.hash = `#/project/${project.id}`;
    resetFiles();
    loadFileTree();
    loadHistory(project.id);
  };

  const handleDelete = async (id: string) => {
    if (pendingDeleteId !== id) {
      setPendingDeleteId(id);
      return;
    }
    setPendingDeleteId(null);
    closeMenu();
    const wasSelected = currentProject?.id === id;
    await deleteProject(id);
    if (wasSelected) {
      const next = useSessionStore.getState().currentProject;
      if (next) {
        window.location.hash = `#/project/${next.id}`;
        resetFiles();
        loadFileTree();
        clearMessages();
        loadHistory(next.id);
      } else {
        window.location.hash = '';
        resetFiles();
        clearMessages();
      }
    }
  };

  const startRename = (project: typeof projects[number]) => {
    closeMenu();
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
    closeMenu();
    if (!project.summary) return;
    try {
      const parsedSummary = JSON.parse(project.summary) as ProjectSummary;
      setSummaryModal({ projectName: project.name, summary: parsedSummary });
    } catch (err) {
      console.error('Failed to parse project summary:', err);
    }
  };

  const menuProject = projects.find((p) => p.id === menuProjectId);
  const canSearchProjects = projects.length > 10;
  const normalizedSearch = canSearchProjects ? searchQuery.trim().toLowerCase() : '';
  const visibleProjects = normalizedSearch
    ? projects.filter((p) => p.name.toLowerCase().includes(normalizedSearch))
    : projects;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3">
        <FlowBrand size="sm" />
        <div className="flex items-center gap-0.5">
          {onCollapse && (
            <Button variant="ghost" size="icon-sm" onClick={onCollapse} title={t('sidebar.collapseSidebar')}>
              <PanelLeftClose size={14} className="text-primary/60" />
            </Button>
          )}
        </div>
      </div>

      {/* New project button */}
      {canCreate && (
        <div className="px-3 mb-2">
          {showInput ? (
            <div className="flex gap-1">
              <Input
                autoFocus
                placeholder={t('common.projectName')}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleCreate();
                  if (e.key === 'Escape') setShowInput(false);
                }}
              />
              <Button size="sm" onClick={handleCreate}>{t('common.add')}</Button>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowInput(true)}
              disabled={isCreating}
              className="w-full justify-start gap-2"
            >
              <Plus size={14} className="text-primary" />
              {t('sidebar.newProject')}
            </Button>
          )}
        </div>
      )}

      {/* Creating indicator */}
      {isCreating && (
        <div className="flex items-center gap-2 mx-3 px-2 py-2.5 mb-2 rounded-md bg-background border border-border text-[13px] text-muted-foreground">
          <Loader2 size={14} className="shrink-0 animate-spin text-primary" />
          {t('sidebar.scaffolding')}
        </div>
      )}

      {/* Project search */}
      {canSearchProjects && (
        <div className="px-3 mb-2">
          <div className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg">
            <Search size={14} className="shrink-0 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={t('sidebar.searchPlaceholder')}
              data-testid="project-search"
              className="flex-1 text-[13px] bg-transparent"
            />
          </div>
        </div>
      )}

      {/* Project list */}
      <div className="flex-1 overflow-auto px-2">
        {visibleProjects.map((project) => {
          const isActive = currentProject?.id === project.id;
          const colorClass = getProjectColor(project.name);
          return (
            <div key={project.id}>
              <div
                onClick={() => handleSelect(project)}
                data-testid={`project-item-${project.id}`}
                className={`group flex items-center gap-2.5 px-2 py-1.5 cursor-pointer mb-0.5 transition-colors duration-100 rounded-md ${isActive ? 'bg-muted/60' : 'hover:bg-muted/30'
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
                  <span className="flex-1 text-[13px] truncate">
                    {project.name}
                    {project.role && (
                      <span className="ml-1.5 text-[10px] text-muted-foreground bg-muted/60 px-1.5 py-0.5 rounded">
                        {project.role}
                      </span>
                    )}
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="icon-sm"
                  popoverTarget="project-menu"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (menuProjectId !== project.id && menuRef.current?.matches(':popover-open')) {
                      e.preventDefault();
                    }
                    setMenuProjectId(project.id);
                  }}
                  style={{ anchorName: anchorName(project.id) } as CSSProperties}
                  className="opacity-0 group-hover:opacity-40 hover:!opacity-100 shrink-0"
                >
                  <MoreHorizontal size={14} />
                </Button>
              </div>
            </div>
          );
        })}
        {normalizedSearch && visibleProjects.length === 0 && (
          <div className="px-2 py-2 text-[13px] text-muted-foreground">
            {t('sidebar.noProjectsMatch')}
          </div>
        )}
      </div>

      <div
        ref={menuRef}
        id="project-menu"
        popover="auto"
        onToggle={(e) => {
          if ((e as unknown as ToggleEvent).newState === 'closed') setPendingDeleteId(null);
        }}
        style={menuProject ? ({ positionAnchor: anchorName(menuProject.id) } as CSSProperties) : undefined}
        className="anchored-menu min-w-35 bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] py-1"
      >
        {menuProject && (
          <>
            {(!menuProject.role || MANAGE_ROLES.has(menuProject.role)) && (
              <button
                onClick={() => startRename(menuProject)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
              >
                <Pencil size={13} className="text-muted-foreground" />
                {t('sidebar.rename')}
              </button>
            )}
            {menuProject.summary && (
              <button
                onClick={() => handleShowSummary(menuProject)}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
              >
                <Info size={13} className="text-muted-foreground" />
                {t('sidebar.summary')}
              </button>
            )}
            {(!menuProject.role || MANAGE_ROLES.has(menuProject.role)) && (
              <button
                onClick={() => {
                  closeMenu();
                  setShareModal({ projectId: menuProject.id, projectName: menuProject.name, ownerUserId: menuProject.user_id });
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
              >
                <Share2 size={13} className="text-muted-foreground" />
                {t('sharing.share', 'Share')}
              </button>
            )}
            {userStatus?.is_admin && (
              <button
                onClick={async () => {
                  closeMenu();
                  try {
                    await reapProject(menuProject.id);
                  } catch { /* sandbox may already be reaped */ }
                }}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left"
              >
                <Moon size={13} className="text-muted-foreground" />
                {t('sidebar.sleep', 'Sleep')}
              </button>
            )}
            {(!menuProject.role || DELETE_ROLES.has(menuProject.role)) && (
              <button
                onClick={() => handleDelete(menuProject.id)}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-[13px] transition-colors text-left ${pendingDeleteId === menuProject.id
                  ? 'text-destructive bg-destructive/10'
                  : 'text-foreground hover:bg-muted/50'
                  }`}
              >
                <Trash2 size={13} className={pendingDeleteId === menuProject.id ? 'text-destructive' : 'text-muted-foreground'} />
                {pendingDeleteId === menuProject.id ? t('sidebar.confirmDelete') : t('common.delete')}
              </button>
            )}
          </>
        )}
      </div>

      {/* Bottom: Settings + Admin */}
      <div className="border-t border-border px-3 py-2 space-y-0.5">
        {userStatus?.is_admin && (
          <Button variant="ghost" size="sm" onClick={onOpenAdmin} className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground">
            <Shield size={14} className="text-warning/70" />
            <span className="text-[13px]">{t('admin.title', 'Platform Users')}</span>
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onOpenSettings} className="w-full justify-start gap-2 text-muted-foreground hover:text-foreground">
          <Settings size={14} className="text-primary/70" />
          <span className="text-[13px]">{t('common.settings')}</span>
        </Button>
      </div>

      {summaryModal && (
        <SummaryModal
          projectName={summaryModal.projectName}
          summary={summaryModal.summary}
          onClose={() => setSummaryModal(null)}
        />
      )}

      {shareModal && (
        <ShareModal
          projectId={shareModal.projectId}
          projectName={shareModal.projectName}
          ownerUserId={shareModal.ownerUserId}
          onClose={() => setShareModal(null)}
        />
      )}
    </div>
  );
}
