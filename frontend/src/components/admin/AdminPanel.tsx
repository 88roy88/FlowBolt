import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, User, Users } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { AdapiSearch } from './AdapiSearch';
import type { PlatformGroup } from '../../types';
import * as api from '../../services/api';

interface PlatformUser {
  user_id: string;
  invited_by: string;
  created_at: string;
}

export function AdminPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [groups, setGroups] = useState<PlatformGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([api.fetchPlatformUsers(), api.fetchPlatformGroups()])
      .then(([u, g]) => { setUsers(u); setGroups(g); })
      .catch(() => setError('Failed to load platform access'))
      .finally(() => setLoading(false));
  }, []);

  const handleInviteUser = async (samAccountName: string) => {
    setError('');
    try {
      const user = await api.invitePlatformUser(samAccountName);
      setUsers((prev) => [user, ...prev.filter((u) => u.user_id !== user.user_id)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to invite user');
    }
  };

  const handleInviteGroup = async (groupId: string, groupName: string) => {
    setError('');
    try {
      const group = await api.invitePlatformGroup(groupId, groupName);
      setGroups((prev) => [group, ...prev.filter((g) => g.group_id !== group.group_id)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to invite group');
    }
  };

  const handleRevokeUser = async (targetUserId: string) => {
    try {
      await api.revokePlatformUser(targetUserId);
      setUsers((prev) => prev.filter((u) => u.user_id !== targetUserId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to revoke user');
    }
  };

  const handleRevokeGroup = async (groupId: string) => {
    try {
      await api.revokePlatformGroup(groupId);
      setGroups((prev) => prev.filter((g) => g.group_id !== groupId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to revoke group');
    }
  };

  const isEmpty = users.length === 0 && groups.length === 0;

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="w-[440px]">
        <DialogClose onClose={onClose} />
        <DialogTitle className="mb-4">{t('admin.title', 'Platform Users')}</DialogTitle>

        {/* Directory search — hover a result and invite the user or group */}
        <AdapiSearch
          onInviteUser={(u) => handleInviteUser(u.sAMAccountName)}
          onInviteGroup={(g) => handleInviteGroup(g.distinguishedName, g.displayName)}
        />

        {error && (
          <p className="text-destructive text-xs mt-2">{error}</p>
        )}

        {/* Platform access list — direct users and granted groups */}
        <div className="border-t border-border mt-3 pt-3 max-h-[300px] overflow-auto space-y-1">
          {loading ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
          ) : isEmpty ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noUsers', 'No platform users yet')}</p>
          ) : (
            <>
              {users.map((u) => (
                <div key={`u:${u.user_id}`} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                  <User size={13} className="shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-[13px] truncate">{u.user_id}</span>
                  <span className="text-muted-foreground text-xs shrink-0">
                    {u.invited_by === 'system' ? 'system' : `by ${u.invited_by}`}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleRevokeUser(u.user_id)}
                    className="opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 size={13} className="text-destructive" />
                  </Button>
                </div>
              ))}
              {groups.map((g) => (
                <div key={`g:${g.group_id}`} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                  <Users size={13} className="shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-[13px] truncate">{g.group_name || g.group_id}</span>
                  <span className="text-muted-foreground text-xs shrink-0">
                    {g.invited_by === 'system' ? 'system' : `by ${g.invited_by}`}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleRevokeGroup(g.group_id)}
                    className="opacity-0 group-hover:opacity-100"
                  >
                    <Trash2 size={13} className="text-destructive" />
                  </Button>
                </div>
              ))}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
