import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { UserPlus, Trash2, Crown } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import type { AssignableRole, ProjectMember } from '../../types';
import * as api from '../../services/api';

const ROLES: { value: AssignableRole; label: string }[] = [
  { value: 'viewer', label: 'Viewer' },
  { value: 'editor', label: 'Editor' },
  { value: 'publisher', label: 'Publisher' },
  { value: 'maintainer', label: 'Maintainer' },
];

export function ShareModal({ projectId, projectName, ownerUserId, onClose }: {
  projectId: string;
  projectName: string;
  ownerUserId?: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState<AssignableRole>('viewer');
  const [error, setError] = useState('');

  useEffect(() => {
    api.fetchProjectMembers(projectId)
      .then(setMembers)
      .catch(() => setError('Failed to load members'))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleAdd = async () => {
    const trimmed = userId.trim();
    if (!trimmed) return;
    setError('');
    try {
      const member = await api.addProjectMember(projectId, trimmed, role);
      setMembers((prev) => [...prev, member]);
      setUserId('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add member');
    }
  };

  const handleUpdateRole = async (targetUserId: string, newRole: AssignableRole) => {
    try {
      await api.updateProjectMemberRole(projectId, targetUserId, newRole);
      setMembers((prev) => prev.map((m) => m.user_id === targetUserId ? { ...m, role: newRole } : m));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role');
    }
  };

  const handleRemove = async (targetUserId: string) => {
    try {
      await api.removeProjectMember(projectId, targetUserId);
      setMembers((prev) => prev.filter((m) => m.user_id !== targetUserId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to remove member');
    }
  };

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

        {/* Add member form */}
        <div className="flex gap-2 mb-3">
          <Input
            placeholder={t('sharing.userIdPlaceholder', 'User ID')}
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
            className="flex-1"
          />
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as AssignableRole)}
            className="px-2 py-1.5 text-[13px] bg-background border border-border rounded-md"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
          <Button size="sm" onClick={handleAdd}>
            <UserPlus size={14} />
          </Button>
        </div>

        {error && (
          <p className="text-destructive text-xs mb-2">{error}</p>
        )}

        {/* Members list */}
        <div className="max-h-[240px] overflow-auto space-y-1">
          {loading ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('common.loading', 'Loading...')}</p>
          ) : members.length === 0 ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('sharing.noMembers', 'No members yet')}</p>
          ) : (
            members.map((m) => (
              <div key={m.user_id} className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/30 group">
                <span className="flex-1 text-[13px] truncate">{m.user_id}</span>
                <select
                  value={m.role}
                  onChange={(e) => handleUpdateRole(m.user_id, e.target.value as AssignableRole)}
                  className="px-1.5 py-1 text-xs bg-background border border-border rounded"
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => handleRemove(m.user_id)}
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
