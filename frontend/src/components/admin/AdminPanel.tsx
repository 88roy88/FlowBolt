import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, User, Users } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { AdapiSearch } from './AdapiSearch';
import type { PlatformGroup, PlatformUser } from '../../types';
import * as api from '../../services/api';

// Rows whose id is in `hits` sort first; ties preserve order under a stable sort.
function rankHit(hits: Set<string>, a: string, b: string): number {
  const aHit = hits.has(a.toLowerCase());
  const bHit = hits.has(b.toLowerCase());
  return aHit === bHit ? 0 : aHit ? -1 : 1;
}

export function AdminPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [groups, setGroups] = useState<PlatformGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [highlightedUserIds, setHighlightedUserIds] = useState<string[]>([]);
  const [highlightedGroupIds, setHighlightedGroupIds] = useState<string[]>([]);

  // Lowercased for case-insensitive matching: stored user_id comes from a token
  // email claim, whose casing can differ from the directory mail.
  const memberIds = useMemo(() => new Set(users.map((u) => u.user_id.toLowerCase())), [users]);
  const groupIds = useMemo(() => new Set(groups.map((g) => g.group_id.toLowerCase())), [groups]);
  const highlightedUserSet = useMemo(
    () => new Set(highlightedUserIds.map((id) => id.toLowerCase())),
    [highlightedUserIds],
  );
  const highlightedGroupSet = useMemo(
    () => new Set(highlightedGroupIds.map((id) => id.toLowerCase())),
    [highlightedGroupIds],
  );

  const orderedUsers = useMemo(
    () => [...users].sort((a, b) => rankHit(highlightedUserSet, a.user_id, b.user_id)),
    [users, highlightedUserSet],
  );
  const orderedGroups = useMemo(
    () => [...groups].sort((a, b) => rankHit(highlightedGroupSet, a.group_id, b.group_id)),
    [groups, highlightedGroupSet],
  );

  useEffect(() => {
    Promise.all([api.fetchPlatformUsers(), api.fetchPlatformGroups()])
      .then(([u, g]) => { setUsers(u); setGroups(g); })
      .catch(() => setError('Failed to load platform access'))
      .finally(() => setLoading(false));
  }, []);

  const handleInviteUser = async (email: string, displayName: string) => {
    setError('');
    try {
      const user = await api.invitePlatformUser(email, displayName);
      setUsers((prev) => [user, ...prev.filter((u) => u.user_id !== user.user_id)]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to invite user');
    }
  };

  const handleInviteGroup = async (groupId: string, groupName: string, email: string) => {
    setError('');
    try {
      const group = await api.invitePlatformGroup(groupId, groupName, email);
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
      <DialogContent className="w-[440px] max-h-[85vh] flex flex-col overflow-hidden">
        <DialogClose onClose={onClose} />

        <div className="shrink-0">
          <DialogTitle className="mb-4">{t('admin.title', 'Platform Users')}</DialogTitle>

          <AdapiSearch
            onInviteUser={(u) => handleInviteUser(u.mail, u.displayName)}
            onInviteGroup={(g) => handleInviteGroup(g.distinguishedName, g.displayName, g.mail)}
            existingUserIds={memberIds}
            onExistingUsersMatched={setHighlightedUserIds}
            existingGroupIds={groupIds}
            onExistingGroupsMatched={setHighlightedGroupIds}
          />

          {error && (
            <p className="text-destructive text-xs mt-2">{error}</p>
          )}
        </div>

        {/* min-h-0 lets this scroll within the dialog's max-height instead of overflowing. */}
        <div className="border-t border-border mt-3 pt-3 flex-auto min-h-0 overflow-auto space-y-1">
          {loading ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
          ) : isEmpty ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noUsers', 'No platform users yet')}</p>
          ) : (
            <>
              {orderedUsers.map((u) => {
                const highlighted = highlightedUserSet.has(u.user_id.toLowerCase());
                return (
                <div
                  key={`u:${u.user_id}`}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-md group transition-colors ${
                    highlighted
                      ? 'bg-primary/15 ring-1 ring-inset ring-primary/50'
                      : 'hover:bg-muted/30'
                  }`}
                >
                  <User size={13} className={`shrink-0 ${highlighted ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="flex-1 min-w-0">
                    <span className={`block text-[13px] truncate ${highlighted ? 'font-semibold' : ''}`}>
                      {u.display_name || u.user_id}
                    </span>
                    {u.display_name && (
                      <span className="block text-xs text-muted-foreground truncate">{u.user_id}</span>
                    )}
                  </span>
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
                );
              })}
              {orderedGroups.map((g) => {
                const highlighted = highlightedGroupSet.has(g.group_id.toLowerCase());
                return (
                <div
                  key={`g:${g.group_id}`}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-md group transition-colors ${
                    highlighted
                      ? 'bg-primary/15 ring-1 ring-inset ring-primary/50'
                      : 'hover:bg-muted/30'
                  }`}
                >
                  <Users size={13} className={`shrink-0 ${highlighted ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="flex-1 min-w-0">
                    <span className={`block text-[13px] truncate ${highlighted ? 'font-semibold' : ''}`}>
                      {g.group_name || g.group_id}
                    </span>
                    {g.email && <span className="block text-xs text-muted-foreground truncate">{g.email}</span>}
                  </span>
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
                );
              })}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
