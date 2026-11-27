import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Shield } from 'lucide-react';
import { AdminPanel } from '../admin/AdminPanel';
import { Button } from '../ui/button';
import { FlowBrand } from '../ui/flow-logo';
import { useClientConfigQuery } from '../../hooks/useClientConfig';
import * as api from '../../services/api';

const LAST_ANSWER_KEY = 'workspaces-disabled';

function readLastAnswer(): boolean | null {
  try {
    const stored = localStorage.getItem(LAST_ANSWER_KEY);
    return stored === null ? null : stored === 'true';
  } catch {
    return null;
  }
}

function saveLastAnswer(disabled: boolean) {
  try {
    localStorage.setItem(LAST_ANSWER_KEY, String(disabled));
  } catch {
    // A stale "not blocked" that can't be overwritten would reload the page forever.
    try { localStorage.removeItem(LAST_ANSWER_KEY); } catch {}
  }
}

/** Keeps the app from mounting while the disable_workspaces kill switch is on for this user. */
export function WorkspaceGate({ children }: { children: ReactNode }) {
  // isFetched, not isPending: a refetch after a failed first load goes back to pending and would remount the app.
  const { data, isFetched } = useClientConfigQuery();
  // The last answer stands in until the server replies, so a slow backend doesn't hold returning users on the spinner.
  const [lastAnswer] = useState(readLastAnswer);
  // The same rule as the backend's workspace_gate.
  const answer =
    data && data.features.includes('disable_workspaces') && !data.features.includes('disable_workspaces_exempt');
  const disabled = answer ?? lastAnswer ?? false;
  const waiting = !isFetched && lastAnswer === null;
  const [appStarted, setAppStarted] = useState(false);

  // Declared before the reload below, which needs the new answer to be saved already.
  useEffect(() => {
    if (answer !== undefined) saveLastAnswer(answer);
  }, [answer]);

  useEffect(() => {
    if (waiting) return;
    if (!disabled) setAppStarted(true);
    // The app's sockets, pollers and preview iframe outlive an unmount; only a reload drops them all.
    else if (appStarted) window.location.reload();
  }, [waiting, disabled, appStarted]);

  if (waiting) {
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
            "You can't work on projects right now. Published apps still work. Refresh the page later to check again.",
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
