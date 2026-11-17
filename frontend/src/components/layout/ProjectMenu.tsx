import { useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { MoreHorizontal, Trash2, Info, Pencil, Moon, Share2 } from 'lucide-react';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { DELETE_ROLES, MANAGE_ROLES, type Project, type ProjectSummary } from '../../types';
import { reapProject } from '../../services/api';
import type { useProjectRename } from '../../hooks/useProjectRename';
import { Button } from '../ui/button';
import { SummaryModal } from './SummaryModal';
import { ShareModal } from '../sharing/ShareModal';

const anchorName = (id: string) => `--a${id.replace(/-/g, '')}`;

const isOpen = (menuId: string) => document.getElementById(menuId)?.matches(':popover-open') ?? false;

type RenameState = ReturnType<typeof useProjectRename>;

export function ProjectRenameInput({ rename }: { rename: RenameState }) {
  return (
    <input
      autoFocus
      value={rename.renameValue}
      onChange={(e) => rename.setRenameValue(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') rename.submit();
        if (e.key === 'Escape') {
          // Don't let Escape also light-dismiss an enclosing popover
          e.stopPropagation();
          rename.cancel();
        }
      }}
      onBlur={rename.submit}
      className="flex-1 min-w-0 text-[13px] bg-background border border-border rounded px-1.5 py-0.5"
    />
  );
}

/** The "⋯" button on a project row; opens the shared ProjectMenu anchored to itself. */
export function ProjectMenuButton({ menuId, project, activeProjectId, onOpen }: {
  menuId: string;
  project: Project;
  activeProjectId: string | null;
  onOpen: (id: string) => void;
}) {
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      popoverTarget={menuId}
      onClick={(e) => {
        e.stopPropagation();
        // Switching rows while open: keep the menu open and just re-anchor it
        if (activeProjectId !== project.id && isOpen(menuId)) e.preventDefault();
        onOpen(project.id);
      }}
      style={{ anchorName: anchorName(project.id) } as CSSProperties}
      className="relative opacity-0 group-hover:opacity-40 focus-visible:opacity-100 hover:!opacity-100 shrink-0"
    >
      <MoreHorizontal size={14} />
    </Button>
  );
}

type ProjectMenuProps = {
  menuId: string;
  project: Project | undefined;
  onRename: (project: Project) => void;
  /** Called before a modal opens, e.g. so an enclosing popover can close first. */
  onOpenModal?: () => void;
};

/** Rename / summary / share / sleep / delete menu for a project, plus the modals it opens. */
export function ProjectMenu({ menuId, project, onRename, onOpenModal }: ProjectMenuProps) {
  const { t } = useTranslation();
  const currentProject = useSessionStore((s) => s.currentProject);
  const userStatus = useSessionStore((s) => s.userStatus);
  const deleteProject = useSessionStore((s) => s.deleteProject);
  const goHome = useSessionStore((s) => s.goHome);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [summaryModal, setSummaryModal] = useState<{ projectName: string; summary: ProjectSummary; } | null>(null);
  const [shareModal, setShareModal] = useState<{ projectId: string; projectName: string; ownerUserId?: string; } | null>(null);

  const closeMenu = () => document.getElementById(menuId)?.hidePopover();

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
      goHome();
      useFilesStore.getState().reset();
    }
  };

  const handleShowSummary = (p: Project) => {
    closeMenu();
    if (!p.summary) return;
    try {
      setSummaryModal({ projectName: p.name, summary: JSON.parse(p.summary) as ProjectSummary });
      onOpenModal?.();
    } catch (err) {
      console.error('Failed to parse project summary:', err);
    }
  };

  const canManage = !project?.role || MANAGE_ROLES.has(project.role);
  const canDelete = !project?.role || DELETE_ROLES.has(project.role);
  const itemClass = 'w-full flex items-center gap-2 px-3 py-1.5 text-[13px] text-foreground hover:bg-muted/50 transition-colors text-left';

  return (
    <>
      <div
        id={menuId}
        popover="auto"
        onToggle={(e) => {
          if ((e as unknown as ToggleEvent).newState === 'closed') setPendingDeleteId(null);
        }}
        style={project ? ({ positionAnchor: anchorName(project.id) } as CSSProperties) : undefined}
        className="anchored-menu min-w-35 bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] py-1"
      >
        {project && (
          <>
            {canManage && (
              <button onClick={() => { closeMenu(); onRename(project); }} className={itemClass}>
                <Pencil size={13} className="text-muted-foreground" />
                {t('sidebar.rename')}
              </button>
            )}
            {project.summary && (
              <button onClick={() => handleShowSummary(project)} className={itemClass}>
                <Info size={13} className="text-muted-foreground" />
                {t('sidebar.summary')}
              </button>
            )}
            {canManage && (
              <button
                onClick={() => {
                  closeMenu();
                  setShareModal({ projectId: project.id, projectName: project.name, ownerUserId: project.user_id });
                  onOpenModal?.();
                }}
                className={itemClass}
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
                    await reapProject(project.id);
                  } catch { /* sandbox may already be reaped */ }
                }}
                className={itemClass}
              >
                <Moon size={13} className="text-muted-foreground" />
                {t('sidebar.sleep', 'Sleep')}
              </button>
            )}
            {canDelete && (
              <button
                onClick={() => handleDelete(project.id)}
                className={`w-full flex items-center gap-2 px-3 py-1.5 text-[13px] transition-colors text-left ${pendingDeleteId === project.id
                  ? 'text-destructive bg-destructive/10'
                  : 'text-foreground hover:bg-muted/50'
                  }`}
              >
                <Trash2 size={13} className={pendingDeleteId === project.id ? 'text-destructive' : 'text-muted-foreground'} />
                {pendingDeleteId === project.id ? t('sidebar.confirmDelete') : t('common.delete')}
              </button>
            )}
          </>
        )}
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
    </>
  );
}
