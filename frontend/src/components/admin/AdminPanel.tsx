import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { UserPlus, Trash2, ExternalLink } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { cn } from '@/lib/utils';
import * as api from '../../services/api';

interface PlatformUser {
  user_id: string;
  invited_by: string;
  created_at: string;
}

interface PublishedApp {
  project_id: string;
  name: string;
  owner_id: string;
  project_url: string;
  public_path: string;
  published_at: string;
}

type Tab = 'users' | 'published';

export function AdminPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('users');
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');
  const [apps, setApps] = useState<PublishedApp[]>([]);
  const [appsLoading, setAppsLoading] = useState(true);

  useEffect(() => {
    api.fetchPlatformUsers()
      .then(setUsers)
      .catch(() => setError('Failed to load users'))
      .finally(() => setLoading(false));
  }, []);

  // Lazy: only hit the endpoint once the tab is actually opened.
  useEffect(() => {
    if (tab !== 'published') return;
    setAppsLoading(true);
    api.fetchPublishedApps()
      .then(setApps)
      .catch(() => setError('Failed to load published apps'))
      .finally(() => setAppsLoading(false));
  }, [tab]);

  const handleInvite = async () => {
    const trimmed = userId.trim();
    if (!trimmed) return;
    setError('');
    try {
      const user = await api.invitePlatformUser(trimmed);
      setUsers((prev) => [user, ...prev]);
      setUserId('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to invite user');
    }
  };

  const handleRevoke = async (targetUserId: string) => {
    try {
      await api.revokePlatformUser(targetUserId);
      setUsers((prev) => prev.filter((u) => u.user_id !== targetUserId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to revoke user');
    }
  };

  const tabButton = (value: Tab, label: string) => (
    <button
      type="button"
      onClick={() => { setTab(value); setError(''); }}
      className={cn(
        'text-[13px] pb-1.5 border-b-2 transition-colors',
        tab === value
          ? 'border-primary text-foreground'
          : 'border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      {label}
    </button>
  );

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="w-[560px]">
        <DialogClose onClose={onClose} />
        <DialogTitle className="mb-3">{t('admin.title', 'Admin')}</DialogTitle>

        {/* Tabs */}
        <div className="flex gap-4 mb-3 border-b border-border">
          {tabButton('users', t('admin.usersTab', 'Platform Users'))}
          {tabButton('published', t('admin.publishedTab', 'Published Apps'))}
        </div>

        {tab === 'users' && (
          <>
            {/* Invite form */}
            <div className="flex gap-2 mb-3">
              <Input
                placeholder={t('admin.userIdPlaceholder', 'User ID to invite')}
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') handleInvite(); }}
                className="flex-1"
              />
              <Button size="sm" onClick={handleInvite}>
                <UserPlus size={14} className="me-1" />
                {t('admin.invite', 'Invite')}
              </Button>
            </div>

            {error && (
              <p className="text-destructive text-xs mb-2">{error}</p>
            )}

            {/* Users list */}
            <div className="max-h-[300px] overflow-auto space-y-1">
              {loading ? (
                <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
              ) : users.length === 0 ? (
                <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noUsers', 'No platform users yet')}</p>
              ) : (
                users.map((u) => (
                  <div key={u.user_id} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                    <span className="flex-1 text-[13px] truncate">{u.user_id}</span>
                    <span className="text-muted-foreground text-xs shrink-0">
                      {u.invited_by === 'system' ? 'system' : `by ${u.invited_by}`}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => handleRevoke(u.user_id)}
                      className="opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 size={13} className="text-destructive" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {tab === 'published' && (
          <>
            {error && (
              <p className="text-destructive text-xs mb-2">{error}</p>
            )}

            {/* Published apps list */}
            <div className="max-h-[300px] overflow-auto space-y-1">
              {appsLoading ? (
                <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
              ) : apps.length === 0 ? (
                <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noPublished', 'No published apps yet')}</p>
              ) : (
                apps.map((a) => (
                  <div
                    key={a.project_id}
                    className="grid grid-cols-[1fr_140px_160px_90px] gap-2 items-center px-2 py-1.5 rounded-md hover:bg-muted/30 group"
                  >
                    <span className="min-w-0 text-[13px] truncate" title={a.project_id}>{a.name}</span>
                    <span className="text-muted-foreground text-xs text-left truncate" title={a.owner_id}>
                      {a.owner_id}
                    </span>
                    <a
                      href={a.public_path}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline min-w-0"
                    >
                      <span className="truncate">{a.project_url}</span>
                      <ExternalLink size={11} className="shrink-0" />
                    </a>
                    <span className="text-muted-foreground text-xs">
                      {new Date(a.published_at).toLocaleDateString()}
                    </span>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
