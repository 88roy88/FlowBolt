import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Code2, ExternalLink, Eye, Globe, Settings, Share2, Shield } from 'lucide-react';
import { useSessionStore } from '../../stores/session';
import { usePublishStore } from '../../stores/publish';
import { useTabPanelStore, type PanelTab } from '../../stores/tabPanel';
import { MANAGE_ROLES, PUBLISH_ROLES } from '../../types';
import { FlowHomeLink } from '../ui/flow-logo';
import { Button } from '../ui/button';
import { ShareModal } from '../sharing/ShareModal';
import { ProjectSwitcher } from './ProjectSwitcher';

type TopBarProps = {
  /** An open project with a workspace: show panel tabs, share and publish. */
  showProjectActions: boolean;
  /** Classic layout's Preview / Code tabs (the flexible layout has its own pane toggles). */
  showPanelTabs: boolean;
  onOpenSettings: () => void;
  onOpenAdmin: () => void;
};

const PANEL_TABS: { tab: PanelTab; Icon: typeof Eye; labelKey: string }[] = [
  { tab: 'preview', Icon: Eye, labelKey: 'preview.title' },
  { tab: 'code', Icon: Code2, labelKey: 'preview.code' },
];

/** Slim top navigation used instead of the project sidebar. */
export function TopBar({ showProjectActions, showPanelTabs, onOpenSettings, onOpenAdmin }: TopBarProps) {
  const { t } = useTranslation();
  const isAdmin = useSessionStore((s) => s.userStatus?.is_admin);
  const project = useSessionStore((s) => s.currentProject);
  const panelTab = useTabPanelStore((s) => s.tab);
  const setPanelTab = useTabPanelStore((s) => s.setTab);
  const [showShare, setShowShare] = useState(false);

  const actions = showProjectActions && project;
  const isPublished = !!project?.published_url;
  const canShare = !project?.role || MANAGE_ROLES.has(project.role);
  const canPublish = !project?.role || PUBLISH_ROLES.has(project.role);

  return (
    <div className="flex items-center gap-1 h-11 px-2 shrink-0 bg-surface border-b border-border" data-testid="topbar">
      <FlowHomeLink title={t('topbar.home')} />
      <span className="text-muted-foreground/50 select-none" aria-hidden>/</span>
      <ProjectSwitcher />

      <div className="flex-1" />

      {actions && showPanelTabs && (
        <div className="flex gap-0.5 p-0.5 me-2 rounded-md bg-muted/50" role="tablist" data-testid="topbar-panel-tabs">
          {PANEL_TABS.map(({ tab, Icon, labelKey }) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={panelTab === tab}
              onClick={() => setPanelTab(tab)}
              className={`flex items-center gap-1.5 h-7 px-2.5 rounded text-[12px] font-medium transition-colors ${
                panelTab === tab
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Icon size={13} className={panelTab === tab ? 'text-primary' : ''} />
              {t(labelKey)}
            </button>
          ))}
        </div>
      )}

      {actions && (
        <div className="flex items-center gap-1.5 me-1">
          {canShare && (
            <Button variant="ghost" size="sm" onClick={() => setShowShare(true)} data-testid="topbar-share">
              <Share2 size={14} className="text-primary/70" />
              {t('sharing.share', 'Share')}
            </Button>
          )}
          {isPublished && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(`/shared/${project.published_url}`, '_blank')}
              title={t('preview.viewPublishedApp')}
            >
              <ExternalLink size={14} className="text-primary/70" />
              {t('preview.viewLive')}
            </Button>
          )}
          {canPublish && (
            <Button
              size="sm"
              onClick={() => usePublishStore.getState().open(project.id, project.published_url)}
              data-testid="topbar-publish"
            >
              <Globe size={14} />
              {isPublished ? t('preview.republish') : t('preview.publish')}
            </Button>
          )}
        </div>
      )}

      {actions && <div className="w-px h-5 bg-border mx-1" aria-hidden />}

      {isAdmin && (
        <Button variant="ghost" size="icon-sm" onClick={onOpenAdmin} title={t('admin.title', 'Platform Users')}>
          <Shield size={15} className="text-warning/70" />
        </Button>
      )}
      <Button variant="ghost" size="icon-sm" onClick={onOpenSettings} title={t('common.settings')}>
        <Settings size={15} className="text-primary/70" />
      </Button>

      {showShare && project && (
        <ShareModal
          projectId={project.id}
          projectName={project.name}
          ownerUserId={project.user_id}
          onClose={() => setShowShare(false)}
        />
      )}
    </div>
  );
}
