import { useState, useEffect } from 'react';
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

  useEffect(() => {
    Promise.all([api.fetchProjectMembers(projectId), api.fetchProjectGroups(projectId)])
      .then(([m, g]) => { setMembers(m); setGroups(g); })
      .catch(() => setError('Failed to load members'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleInviteUser = async (userId: string) => {
    setError('');
    try {
      const member = await api.addProjectMember(projectId, userId, newRole);
      setMembers((prev) => [...prev.filter((m) => m.user_id !== member.user_id), member]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add member');
    }
  };

  const handleInviteGroup = async (groupId: string, groupName: string) => {
    setError('');
    try {
      const grant = await api.addProjectGroup(projectId, groupId, groupName, newRole);
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
      <DialogContent className="w-[440px]">
        <DialogClose onClose={onClose} />
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
          onInviteUser={(user) => handleInviteUser(user.sAMAccountName)}
          onInviteGroup={(group) => handleInviteGroup(group.objectGUID, group.displayName)}
        />

        {error && (
          <p className="text-destructive text-xs mt-2">{error}</p>
        )}

        {/* Members & group grants */}
        <div className="border-t border-border mt-3 pt-3 max-h-[280px] overflow-auto space-y-1">
          {loading ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
          ) : isEmpty ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('sharing.noMembers', 'No members yet')}</p>
          ) : (
            <>
              {members.map((m) => (
                <div key={`u:${m.user_id}`} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                  <User size={13} className="shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-[13px] truncate">{m.user_id}</span>
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
              ))}
              {groups.map((g) => (
                <div key={`g:${g.group_id}`} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                  <Users size={13} className="shrink-0 text-muted-foreground" />
                  <span className="flex-1 text-[13px] truncate">{g.group_name || g.group_id}</span>
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
              ))}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
