import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/session';
import { Plus, PanelLeftClose, Loader2, Settings, Shield, Search } from 'lucide-react';
import { FlowBrand } from '../ui/flow-logo';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { isPlainClick, projectHref } from '../../utils/links';
import { openProject, createAndOpenProject } from '../../utils/openProject';
import { useProjectSearch } from '../../hooks/useProjectSearch';
import { ProjectAvatar } from './ProjectAvatar';
import { ProjectMenu, ProjectMenuButton, ProjectRenameInput } from './ProjectMenu';
import { useProjectRename } from '../../hooks/useProjectRename';

type SidebarProps = {
  onCollapse?: () => void;
  onOpenSettings?: () => void;
  onOpenAdmin?: () => void;
};

const MENU_ID = 'project-menu';

export function Sidebar({ onCollapse, onOpenSettings, onOpenAdmin }: SidebarProps) {
  const { t } = useTranslation();
  const currentProject = useSessionStore((s) => s.currentProject);
  const isCreating = useSessionStore((s) => s.isCreating);
  const userStatus = useSessionStore((s) => s.userStatus);
  const search = useProjectSearch();
  const rename = useProjectRename();
  const [newName, setNewName] = useState('');
  const [showInput, setShowInput] = useState(false);
  const [menuProjectId, setMenuProjectId] = useState<string | null>(null);

  const canCreate = userStatus?.is_platform_user || userStatus?.is_admin;

  const handleCreate = async () => {
    const name = newName.trim() || 'New Project';
    setNewName('');
    setShowInput(false);
    await createAndOpenProject(name);
  };

  const menuProject = search.visibleProjects.find((p) => p.id === menuProjectId);

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
      {search.canSearch && (
        <div className="px-3 mb-2">
          <div className="flex items-center gap-2 px-3 py-2 bg-background border border-border rounded-lg">
            {search.isSearching
              ? <Loader2 size={14} className="shrink-0 animate-spin text-muted-foreground" data-testid="project-search-loading" />
              : <Search size={14} className="shrink-0 text-muted-foreground" />}
            <input
              type="text"
              value={search.query}
              onChange={(e) => search.setQuery(e.target.value)}
              placeholder={t('sidebar.searchPlaceholder')}
              data-testid="project-search"
              className="flex-1 text-[13px] bg-transparent"
            />
          </div>
        </div>
      )}

      {/* Project list */}
      <div className={`flex-1 overflow-auto px-2 transition-opacity ${search.isSearching ? 'opacity-50' : ''}`} aria-busy={search.isSearching}>
        {search.visibleProjects.map((project) => {
          const isActive = currentProject?.id === project.id;
          return (
            <div key={project.id}>
              <div
                data-testid={`project-item-${project.id}`}
                className={`group relative flex items-center gap-2.5 px-2 py-1.5 mb-0.5 transition-colors duration-100 rounded-md ${isActive ? 'bg-muted/60' : 'hover:bg-muted/30'
                  }`}
              >
                <ProjectAvatar name={project.name} />
                {rename.renamingId === project.id ? (
                  <ProjectRenameInput rename={rename} />
                ) : (
                  // The link's ::after covers the whole row, so the row clicks (and middle clicks) as a link
                  <a
                    href={projectHref(project.id)}
                    onClick={(e) => {
                      if (!isPlainClick(e)) return;
                      e.preventDefault();
                      openProject(project);
                    }}
                    className="flex-1 text-[13px] text-inherit truncate after:absolute after:inset-0 after:rounded-md"
                  >
                    {project.name}
                    {project.role && (
                      <span className="ml-1.5 text-[10px] text-muted-foreground bg-muted/60 px-1.5 py-0.5 rounded">
                        {project.role}
                      </span>
                    )}
                  </a>
                )}
                <ProjectMenuButton menuId={MENU_ID} project={project} activeProjectId={menuProjectId} onOpen={setMenuProjectId} />
              </div>
            </div>
          );
        })}
        {search.noMatches && (
          <div className="px-2 py-2 text-[13px] text-muted-foreground">
            {t('sidebar.noProjectsMatch')}
          </div>
        )}
        {search.hasMore && (
          <Button
            variant="ghost"
            size="sm"
            onClick={search.loadMore}
            disabled={search.isLoadingMore}
            data-testid="load-more-projects"
            className="w-full my-1 text-[13px] text-muted-foreground hover:text-foreground"
          >
            {search.isLoadingMore && <Loader2 size={14} className="animate-spin" />}
            {t('sidebar.loadMore')}
          </Button>
        )}
      </div>

      <ProjectMenu menuId={MENU_ID} project={menuProject} onRename={rename.start} />

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
    </div>
  );
}
