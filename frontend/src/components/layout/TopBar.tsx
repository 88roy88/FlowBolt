import { useTranslation } from 'react-i18next';
import { Settings, Shield } from 'lucide-react';
import { useSessionStore } from '../../stores/session';
import { FlowHomeLink } from '../ui/flow-logo';
import { Button } from '../ui/button';
import { ProjectSwitcher } from './ProjectSwitcher';

type TopBarProps = {
  onOpenSettings: () => void;
  onOpenAdmin: () => void;
};

/** Slim top navigation used instead of the project sidebar. */
export function TopBar({ onOpenSettings, onOpenAdmin }: TopBarProps) {
  const { t } = useTranslation();
  const isAdmin = useSessionStore((s) => s.userStatus?.is_admin);

  return (
    <div className="flex items-center gap-1 h-11 px-2 shrink-0 bg-surface border-b border-border" data-testid="topbar">
      <FlowHomeLink title={t('topbar.home')} />
      <span className="text-muted-foreground/50 select-none" aria-hidden>/</span>
      <ProjectSwitcher />
      <div className="flex-1" />
      {isAdmin && (
        <Button variant="ghost" size="icon-sm" onClick={onOpenAdmin} title={t('admin.title', 'Platform Users')}>
          <Shield size={15} className="text-warning/70" />
        </Button>
      )}
      <Button variant="ghost" size="icon-sm" onClick={onOpenSettings} title={t('common.settings')}>
        <Settings size={15} className="text-primary/70" />
      </Button>
    </div>
  );
}
