import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, Crown, User, Users } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { AdapiSearch } from '../admin/AdapiSearch';
import type { AssignableRole, ProjectMember, ProjectGroupGrant } from '../../types';
import * as api from '../../services/api';

const ROLES: { value: AssignableRole; label: string }[] = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'editor', label: 'Editor' },
  { value: 'publisher', label: 'Publisher' },
  { value: 'maintainer', label: 'Maintainer' },
];

// Sort comparator: rows whose id is in `hits` (case-insensitive) sort before
// those that aren't; ties preserve input order under a stable sort.
function rankHit(hits: Set<string>, a: string, b: string): number {
  const aHit = hits.has(a.toLowerCase());
  const bHit = hits.has(b.toLowerCase());
  return aHit === bHit ? 0 : aHit ? -1 : 1;
}

function RoleSelect({ value, onChange, className }: {
  value: AssignableRole;
  onChange: (role: AssignableRole) => void;
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as AssignableRole)}
      className={className}
    >
      {ROLES.map((r) => (
        <option key={r.value} value={r.value}>{r.label}</option>
      ))}
    </select>
  );
}

export function ShareModal({ projectId, projectName, ownerUserId, onClose }: {
  projectId: string;
  projectName: string;
  ownerUserId?: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [groups, setGroups] = useState<ProjectGroupGrant[]>([]);
  const [loading, setLoading] = useState(true);
  // Role applied to the next invite made from the search below.
  const [newRole, setNewRole] = useState<AssignableRole>('viewer');
  const [error, setError] = useState('');
  // Existing members/groups whose row should be highlighted because the current
  // directory search matched them (they're already granted, so the search hides
  // them from its own results and points here instead).
  const [highlightedUserIds, setHighlightedUserIds] = useState<string[]>([]);
  const [highlightedGroupIds, setHighlightedGroupIds] = useState<string[]>([]);

  // Ids already granted — lowercased for case-insensitive matching (the stored
  // user_id comes from a token email claim, whose casing can differ from the
  // directory's mail) and memoized so AdapiSearch's effects don't churn.
  const memberIds = useMemo(() => new Set(members.map((m) => m.user_id.toLowerCase())), [members]);
  const groupIds = useMemo(() => new Set(groups.map((g) => g.group_id.toLowerCase())), [groups]);
  const highlightedUserSet = useMemo(
    () => new Set(highlightedUserIds.map((id) => id.toLowerCase())),
    [highlightedUserIds],
  );
  const highlightedGroupSet = useMemo(
    () => new Set(highlightedGroupIds.map((id) => id.toLowerCase())),
    [highlightedGroupIds],
  );

  // Matched-existing rows float to the top of their list. sort() is stable, so
  // everyone else keeps their original order.
  const orderedMembers = useMemo(
    () => [...members].sort((a, b) => rankHit(highlightedUserSet, a.user_id, b.user_id)),
    [members, highlightedUserSet],
  );
  const orderedGroups = useMemo(
    () => [...groups].sort((a, b) => rankHit(highlightedGroupSet, a.group_id, b.group_id)),
    [groups, highlightedGroupSet],
  );

  useEffect(() => {
    Promise.all([api.fetchProjectMembers(projectId), api.fetchProjectGroups(projectId)])
      .then(([m, g]) => { setMembers(m); setGroups(g); })
      .catch(() => setError('Failed to load members'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleInviteUser = async (userId: string, displayName: string) => {
    setError('');
    try {
      const member = await api.addProjectMember(projectId, userId, newRole, displayName);
      setMembers((prev) => [...prev.filter((m) => m.user_id !== member.user_id), member]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add member');
    }
  };

  const handleInviteGroup = async (groupId: string, groupName: string, email: string) => {
    setError('');
    try {
      const grant = await api.addProjectGroup(projectId, groupId, groupName, newRole, email);
      setGroups((prev) => [...prev.filter((g) => g.group_id !== grant.group_id), grant]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add group');
    }
  };

  const handleUpdateMemberRole = async (targetUserId: string, role: AssignableRole) => {
    try {
      await api.updateProjectMemberRole(projectId, targetUserId, role);
      setMembers((prev) => prev.map((m) => m.user_id === targetUserId ? { ...m, role } : m));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role');
    }
  };

  const handleRemoveMember = async (targetUserId: string) => {
    try {
      await api.removeProjectMember(projectId, targetUserId);
      setMembers((prev) => prev.filter((m) => m.user_id !== targetUserId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove member');
    }
  };

  const handleUpdateGroupRole = async (groupId: string, role: AssignableRole) => {
    try {
      await api.updateProjectGroupRole(projectId, groupId, role);
      setGroups((prev) => prev.map((g) => g.group_id === groupId ? { ...g, role } : g));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role');
    }
  };

  const handleRemoveGroup = async (groupId: string) => {
    try {
      await api.removeProjectGroup(projectId, groupId);
      setGroups((prev) => prev.filter((g) => g.group_id !== groupId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove group');
    }
  };

  const isEmpty = members.length === 0 && groups.length === 0;

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent className="w-[440px] flex flex-col overflow-hidden">
        <DialogClose onClose={onClose} />

        {/* Fixed header + search (the search has its own scrollable results). */}
        <div className="shrink-0">
          <DialogTitle className="mb-4">
            {t('sharing.title', 'Share')} — {projectName}
          </DialogTitle>

          {/* Owner display */}
          {ownerUserId && (
            <div className="flex items-center gap-2 px-2 py-1.5 mb-3 rounded-md bg-muted/30 text-[13px]">
              <Crown size={13} className="text-warning shrink-0" />
              <span className="truncate flex-1">{ownerUserId}</span>
              <span className="text-muted-foreground text-xs">{t('sharing.owner', 'Owner')}</span>
            </div>
          )}

          {/* Role applied to invites made from the search */}
          <div className="flex items-center justify-end gap-2 mb-2 text-xs text-muted-foreground">
            <span>{t('sharing.inviteAs', 'Invite as')}</span>
            <RoleSelect
              value={newRole}
              onChange={setNewRole}
              className="px-1.5 py-1 text-xs bg-background border border-border rounded"
            />
          </div>

          {/* Directory search — hover a result and invite the user or group */}
          <AdapiSearch
            onInviteUser={(user) => handleInviteUser(user.mail, user.displayName)}
            onInviteGroup={(group) => handleInviteGroup(group.distinguishedName, group.displayName, group.mail)}
            existingUserIds={memberIds}
            onExistingUsersMatched={setHighlightedUserIds}
            existingGroupIds={groupIds}
            onExistingGroupsMatched={setHighlightedGroupIds}
          />

          {error && (
            <p className="text-destructive text-xs mt-2">{error}</p>
          )}
        </div>

        {/* Members & group grants — its own scrollable region */}
        <div className="border-t border-border mt-3 pt-3 flex-auto min-h-0 overflow-auto space-y-1">
          {loading ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
          ) : isEmpty ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('sharing.noMembers', 'No members yet')}</p>
          ) : (
            <>
              {orderedMembers.map((m) => {
                const highlighted = highlightedUserSet.has(m.user_id.toLowerCase());
                return (
                <div
                  key={`u:${m.user_id}`}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-md group transition-colors ${
                    highlighted
                      ? 'bg-primary/15 ring-1 ring-inset ring-primary/50'
                      : 'hover:bg-muted/30'
                  }`}
                >
                  <User size={13} className={`shrink-0 ${highlighted ? 'text-primary' : 'text-muted-foreground'}`} />
                  <span className="flex-1 min-w-0">
                    <span className={`block text-[13px] truncate ${highlighted ? 'font-semibold' : ''}`}>
                      {m.display_name || m.user_id}
                    </span>
                    {m.display_name && (
                      <span className="block text-xs text-muted-foreground truncate">{m.user_id}</span>
                    )}
                  </span>
                  <RoleSelect
                    value={m.role}
                    onChange={(role) => handleUpdateMemberRole(m.user_id, role)}
                    className="px-1.5 py-1 text-xs bg-background border border-border rounded"
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleRemoveMember(m.user_id)}
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
                  <RoleSelect
                    value={g.role}
                    onChange={(role) => handleUpdateGroupRole(g.group_id, role)}
                    className="px-1.5 py-1 text-xs bg-background border border-border rounded"
                  />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => handleRemoveGroup(g.group_id)}
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
