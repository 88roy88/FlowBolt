import { useRef, useState, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronsUpDown, Loader2, Plus, Search } from 'lucide-react';
import { useSessionStore } from '../../stores/session';
import { useProjectSearch } from '../../hooks/useProjectSearch';
import { isPlainClick, projectHref } from '../../utils/links';
import { openProject, createAndOpenProject } from '../../utils/openProject';
import { Button } from '../ui/button';
import { ProjectAvatar } from './ProjectAvatar';
import { ProjectMenu, ProjectMenuButton, ProjectRenameInput } from './ProjectMenu';
import { useProjectRename } from '../../hooks/useProjectRename';

const SWITCHER_ID = 'project-switcher';
const MENU_ID = 'project-switcher-menu';
const ANCHOR = '--project-switcher';

/** Topbar breadcrumb button that opens a searchable project popover. */
export function ProjectSwitcher() {
  const { t } = useTranslation();
  const currentProject = useSessionStore((s) => s.currentProject);
  const isCreating = useSessionStore((s) => s.isCreating);
  const userStatus = useSessionStore((s) => s.userStatus);
  const search = useProjectSearch();
  const rename = useProjectRename();
  const [menuProjectId, setMenuProjectId] = useState<string | null>(null);
  const [newName, setNewName] = useState('');
  const [showNewInput, setShowNewInput] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const canCreate = userStatus?.is_platform_user || userStatus?.is_admin;
  const close = () => document.getElementById(SWITCHER_ID)?.hidePopover();

  // Small lists aren't searched server-side, so filter them here
  const localQuery = search.canSearch ? '' : search.query.trim().toLowerCase();
  const projects = localQuery
    ? search.visibleProjects.filter((p) => p.name.toLowerCase().includes(localQuery))
    : search.visibleProjects;
  const menuProject = projects.find((p) => p.id === menuProjectId);

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowNewInput(false);
    close();
    await createAndOpenProject(name);
  };

  return (
    <>
      <button
        type="button"
        popoverTarget={SWITCHER_ID}
        data-testid="project-switcher-trigger"
        style={{ anchorName: ANCHOR } as CSSProperties}
        className="flex items-center gap-2 min-w-0 max-w-72 h-8 px-2 rounded-md text-[13px] font-medium hover:bg-muted/40 transition-colors"
      >
        {isCreating ? (
          <>
            <Loader2 size={14} className="shrink-0 animate-spin text-primary" />
            <span className="truncate text-muted-foreground">{t('sidebar.scaffolding')}</span>
          </>
        ) : currentProject ? (
          <>
            <ProjectAvatar name={currentProject.name} size="sm" />
            <span className="truncate">{currentProject.name}</span>
          </>
        ) : (
          <span className="truncate text-muted-foreground">{t('topbar.projects')}</span>
        )}
        <ChevronsUpDown size={14} className="shrink-0 text-muted-foreground" />
      </button>

      <div
        id={SWITCHER_ID}
        popover="auto"
        data-testid="project-switcher"
        onToggle={(e) => {
          const open = (e as unknown as ToggleEvent).newState === 'open';
          if (open) searchRef.current?.focus();
          else {
            search.setQuery('');
            setShowNewInput(false);
          }
        }}
        style={{
          positionAnchor: ANCHOR,
          positionArea: 'block-end span-inline-end',
          insetArea: 'block-end span-inline-end',
        } as CSSProperties}
        className="anchored-menu w-80 bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] p-1"
      >
        <div className="flex items-center gap-2 px-2 py-1.5 mb-1 border-b border-border">
          {search.isSearching
            ? <Loader2 size={14} className="shrink-0 animate-spin text-muted-foreground" />
            : <Search size={14} className="shrink-0 text-muted-foreground" />}
          <input
            ref={searchRef}
            type="text"
            value={search.query}
            onChange={(e) => search.setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && projects[0]) {
                close();
                openProject(projects[0], 'project_switcher');
              }
            }}
            placeholder={t('sidebar.searchPlaceholder')}
            data-testid="project-switcher-search"
            className="flex-1 min-w-0 text-[13px] bg-transparent py-0.5"
          />
        </div>

        <div className={`max-h-80 overflow-auto transition-opacity ${search.isSearching ? 'opacity-50' : ''}`} aria-busy={search.isSearching}>
          {projects.map((project) => {
            const isActive = currentProject?.id === project.id;
            return (
              <div
                key={project.id}
                data-testid={`switcher-item-${project.id}`}
                className={`group relative flex items-center gap-2 px-2 py-1.5 rounded-md transition-colors ${isActive ? 'bg-muted/60' : 'hover:bg-muted/30'}`}
              >
                <ProjectAvatar name={project.name} size="sm" />
                {rename.renamingId === project.id ? (
                  <ProjectRenameInput rename={rename} />
                ) : (
                  <a
                    href={projectHref(project.id)}
                    onClick={(e) => {
                      if (!isPlainClick(e)) return;
                      e.preventDefault();
                      close();
                      if (!isActive) openProject(project, 'project_switcher');
                    }}
                    className="flex-1 min-w-0 flex items-center gap-1.5 text-[13px] text-inherit after:absolute after:inset-0 after:rounded-md"
                  >
                    <span className="truncate">{project.name}</span>
                    {project.role && (
                      <span className="shrink-0 text-[10px] text-muted-foreground bg-muted/60 px-1.5 py-0.5 rounded">
                        {project.role}
                      </span>
                    )}
                  </a>
                )}
                {isActive && <Check size={14} className="shrink-0 text-primary" />}
                <ProjectMenuButton menuId={MENU_ID} project={project} activeProjectId={menuProjectId} onOpen={setMenuProjectId} />
              </div>
            );
          })}
          {(search.noMatches || (localQuery && projects.length === 0)) && (
            <div className="px-2 py-2 text-[13px] text-muted-foreground">{t('sidebar.noProjectsMatch')}</div>
          )}
          {search.hasMore && (
            <Button
              variant="ghost"
              size="sm"
              onClick={search.loadMore}
              disabled={search.isLoadingMore}
              className="w-full my-1 text-[13px] text-muted-foreground hover:text-foreground"
            >
              {search.isLoadingMore && <Loader2 size={14} className="animate-spin" />}
              {t('sidebar.loadMore')}
            </Button>
          )}
        </div>

        {canCreate && (
          <div className="border-t border-border mt-1 pt-1">
            {showNewInput ? (
              <div className="flex gap-1 p-1">
                <input
                  autoFocus
                  placeholder={t('common.projectName')}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreate();
                    if (e.key === 'Escape') {
                      e.stopPropagation();
                      setShowNewInput(false);
                    }
                  }}
                  className="flex-1 min-w-0 text-[13px] bg-background border border-border rounded-md px-2 py-1"
                />
                <Button size="sm" onClick={handleCreate}>{t('common.add')}</Button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowNewInput(true)}
                disabled={isCreating}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] hover:bg-muted/30 transition-colors disabled:opacity-50"
              >
                <Plus size={14} className="text-primary" />
                {t('sidebar.newProject')}
              </button>
            )}
          </div>
        )}
      </div>

      <ProjectMenu menuId={MENU_ID} project={menuProject} onRename={rename.start} onOpenModal={close} />
    </>
  );
}
