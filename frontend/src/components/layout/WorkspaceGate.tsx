import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Shield } from 'lucide-react';
import { AdminPanel } from '../admin/AdminPanel';
import { Button } from '../ui/button';
import { FlowBrand } from '../ui/flow-logo';
import { useClientConfigQuery } from '../../hooks/useClientConfig';
import * as api from '../../services/api';

/** Keeps the app from mounting while the disable_workspaces kill switch is on for this user. */
export function WorkspaceGate({ children }: { children: ReactNode }) {
  // isFetched, not isPending: a poll after a failed first load goes back to pending and would remount the app.
  const { data, isFetched } = useClientConfigQuery();
  const disabled = data?.workspaces_disabled ?? false;
  const [appStarted, setAppStarted] = useState(false);

  useEffect(() => {
    if (!isFetched) return;
    if (!disabled) setAppStarted(true);
    // The app's sockets, pollers and preview iframe outlive an unmount; only a reload drops them all.
    else if (appStarted) window.location.reload();
  }, [isFetched, disabled, appStarted]);

  if (!isFetched) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 select-none">
        <FlowBrand size="lg" />
        <Loader2 size={20} className="animate-spin text-brand" />
      </div>
    );
  }
  return disabled ? <WorkspacesDisabled /> : <>{children}</>;
}

function WorkspacesDisabled() {
  const { t } = useTranslation();
  const isAdmin = useQuery({ queryKey: ['me'], queryFn: api.fetchMe }).data?.is_admin;
  const [showAdminPanel, setShowAdminPanel] = useState(false);

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-8">
      <FlowBrand size="lg" />
      <div role="alert" className="w-full max-w-md px-5 py-4 bg-surface rounded-xl border-2 border-destructive/50 text-center">
        <p className="text-destructive font-semibold mb-1.5">
          {t('app.workspacesDisabled', 'Your workspaces are temporarily unavailable')}
        </p>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t(
            'app.workspacesDisabledDetail',
            "You can't work on projects right now. Published apps still work, and this page will come back on its own.",
          )}
        </p>
      </div>
      {isAdmin && (
        <Button variant="ghost" size="sm" className="gap-1.5" onClick={() => setShowAdminPanel(true)}>
          <Shield size={14} className="text-warning/70" />
          {t('admin.title', 'Admin')}
        </Button>
      )}
      {showAdminPanel && <AdminPanel initialTab="flags" onClose={() => setShowAdminPanel(false)} />}
    </div>
  );
}
