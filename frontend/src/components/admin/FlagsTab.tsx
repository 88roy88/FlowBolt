import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus, User, Users, X } from 'lucide-react';
import { Button } from '../ui/button';
import { LoadingDots } from '../ui/loading-dots';
import { DirectorySearch } from './DirectorySearch';
import { cn } from '@/lib/utils';
import type { FeatureFlag, FlagTarget, FlagTargetType } from '../../types';
import * as api from '../../services/api';
import { CLIENT_CONFIG_QUERY_KEY } from '../../hooks/useClientConfig';

const FLAGS_QUERY_KEY = ['admin', 'flags'];

export function FlagsTab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const flagsQuery = useQuery({ queryKey: FLAGS_QUERY_KEY, queryFn: api.fetchFeatureFlags });
  const [addingTo, setAddingTo] = useState<string | null>(null);
  const [error, setError] = useState('');

  // Every change can flip the admin's own flags too, so refresh the client config alongside the list.
  const run = async (action: () => Promise<unknown>, failure: string) => {
    setError('');
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : failure);
    }
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: FLAGS_QUERY_KEY }),
      queryClient.invalidateQueries({ queryKey: CLIENT_CONFIG_QUERY_KEY }),
    ]);
  };

  const flags = flagsQuery.data ?? [];

  if (flagsQuery.isLoading) {
    return <p className="text-muted-foreground text-xs text-center py-4"><LoadingDots /></p>;
  }
  if (flagsQuery.isError) {
    return <p className="text-destructive text-xs text-center py-4">{t('admin.flagsLoadFailed', 'Failed to load feature flags')}</p>;
  }
  if (flags.length === 0) {
    return <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noFlags', 'No feature flags are defined')}</p>;
  }

  return (
    <div className="space-y-2">
      {error && <p className="text-destructive text-xs">{error}</p>}
      {flags.map((flag) => (
        <FlagRow
          key={flag.key}
          flag={flag}
          adding={addingTo === flag.key}
          onToggleAdding={() => setAddingTo((prev) => (prev === flag.key ? null : flag.key))}
          onUpdate={(changes) => run(() => api.updateFeatureFlag(flag.key, changes), 'Failed to update flag')}
          onAddTarget={(target) => run(() => api.addFlagTarget(flag.key, target), 'Failed to add to flag')}
          onRemoveTarget={(type, id) => run(() => api.removeFlagTarget(flag.key, type, id), 'Failed to remove from flag')}
        />
      ))}
    </div>
  );
}

interface FlagRowProps {
  flag: FeatureFlag;
  adding: boolean;
  onToggleAdding: () => void;
  onUpdate: (changes: { enabled_for_all?: boolean; enabled_for_admins?: boolean }) => Promise<void>;
  onAddTarget: (target: { target_type: FlagTargetType; target_id: string; display_name: string; email?: string }) => Promise<void>;
  onRemoveTarget: (type: FlagTargetType, id: string) => Promise<void>;
}

function FlagRow({ flag, adding, onToggleAdding, onUpdate, onAddTarget, onRemoveTarget }: FlagRowProps) {
  const { t } = useTranslation();
  const [pending, setPending] = useState(false);

  const withPending = async (action: () => Promise<void>) => {
    setPending(true);
    try {
      await action();
    } finally {
      setPending(false);
    }
  };

  // Lowercased to match DirectorySearch's case-insensitive lookup.
  const userIds = useMemo(
    () => new Set(flag.targets.filter((tg) => tg.target_type === 'user').map((tg) => tg.target_id.toLowerCase())),
    [flag.targets],
  );
  const groupIds = useMemo(
    () => new Set(flag.targets.filter((tg) => tg.target_type === 'group').map((tg) => tg.target_id.toLowerCase())),
    [flag.targets],
  );

  const switchBox = (checked: boolean, label: string, changes: { enabled_for_all?: boolean; enabled_for_admins?: boolean }) => (
    <label className={cn('flex items-center gap-1.5 text-xs cursor-pointer select-none', pending && 'opacity-60')}>
      <input
        type="checkbox"
        checked={checked}
        disabled={pending}
        onChange={() => withPending(() => onUpdate(changes))}
        className="cursor-pointer accent-primary"
      />
      {label}
    </label>
  );

  return (
    <div className="rounded-md border border-border px-3 py-2.5">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <code className="text-[13px] font-semibold break-all">{flag.key}</code>
          {flag.description && <p className="text-xs text-muted-foreground mt-0.5">{flag.description}</p>}
        </div>
        <div className="flex items-center gap-3 shrink-0 pt-0.5">
          {switchBox(flag.enabled_for_all, t('admin.flagEveryone', 'Everyone'), { enabled_for_all: !flag.enabled_for_all })}
          {switchBox(flag.enabled_for_admins, t('admin.flagAdmins', 'Admins'), { enabled_for_admins: !flag.enabled_for_admins })}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 mt-2">
        {flag.targets.map((target) => (
          <TargetChip
            key={`${target.target_type}:${target.target_id}`}
            target={target}
            disabled={pending}
            onRemove={() => withPending(() => onRemoveTarget(target.target_type, target.target_id))}
          />
        ))}
        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs gap-1" onClick={onToggleAdding}>
          {adding ? <X size={12} /> : <Plus size={12} />}
          {adding ? t('admin.flagDoneAdding', 'Done') : t('admin.flagAddTarget', 'Add user or group')}
        </Button>
      </div>

      {flag.enabled_for_all && flag.targets.length > 0 && (
        <p className="text-[11px] text-muted-foreground mt-1.5">
          {t('admin.flagTargetsInactive', "On for everyone, so this list doesn't matter until Everyone is turned off.")}
        </p>
      )}

      {adding && (
        <div className="mt-2">
          <DirectorySearch
            actionLabel={t('admin.flagAdd', 'Add')}
            onInviteUser={(u) => withPending(() => onAddTarget({ target_type: 'user', target_id: u.uniqueId, display_name: u.displayName, email: u.mail }))}
            onInviteGroup={(g) => withPending(() => onAddTarget({ target_type: 'group', target_id: g.distinguishedName, display_name: g.displayName, email: g.mail }))}
            existingUserIds={userIds}
            existingGroupIds={groupIds}
          />
        </div>
      )}
    </div>
  );
}

function TargetChip({ target, disabled, onRemove }: { target: FlagTarget; disabled: boolean; onRemove: () => void }) {
  const Icon = target.target_type === 'user' ? User : Users;
  const label = target.display_name || target.target_id;
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs max-w-[220px]"
      title={[target.target_id, target.email, `by ${target.added_by}`].filter(Boolean).join('\n')}
    >
      <Icon size={11} className="shrink-0 text-muted-foreground" />
      <span className="truncate">{label}</span>
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        className="shrink-0 text-muted-foreground hover:text-destructive disabled:opacity-50"
        aria-label={`Remove ${label}`}
      >
        <X size={11} />
      </button>
    </span>
  );
}
