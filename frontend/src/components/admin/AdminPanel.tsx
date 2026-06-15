import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { UserPlus, Trash2 } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import * as api from '../../services/api';

interface PlatformUser {
  user_id: string;
  invited_by: string;
  created_at: string;
}

export function AdminPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api.fetchPlatformUsers()
      .then(setUsers)
      .catch(() => setError('Failed to load users'))
      .finally(() => setLoading(false));
  }, []);

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

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="w-[440px]">
        <DialogClose onClose={onClose} />
        <DialogTitle className="mb-4">{t('admin.title', 'Platform Users')}</DialogTitle>

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
            <UserPlus size={14} className="mr-1" />
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
      </DialogContent>
    </Dialog>
  );
}
