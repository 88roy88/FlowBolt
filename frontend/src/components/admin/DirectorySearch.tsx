import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { User, Users, Search, UserPlus } from 'lucide-react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { LoadingDots } from '../ui/loading-dots';
import { useDebouncedValue } from '../../hooks/useDebounce';
import { searchAdUsers, searchAdGroups } from '../../services/api';
import type { AdUser, AdGroup } from '../../types';

type Filter = 'all' | 'users' | 'groups';

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 300;

interface DirectorySearchProps {
  onInviteUser?: (user: AdUser) => void;
  onInviteGroup?: (group: AdGroup) => void;
  // Lowercased ids already granted; matches are lifted out of results and reported
  // back so the parent highlights them in its own list.
  existingUserIds?: Set<string>;
  onExistingUsersMatched?: (userIds: string[]) => void;
  existingGroupIds?: Set<string>;
  onExistingGroupsMatched?: (groupIds: string[]) => void;
}

export function DirectorySearch({
  onInviteUser,
  onInviteGroup,
  existingUserIds,
  onExistingUsersMatched,
  existingGroupIds,
  onExistingGroupsMatched,
}: DirectorySearchProps) {
  const { t } = useTranslation();
  const canUsers = !!onInviteUser;
  const canGroups = !!onInviteGroup;

  const [filter, setFilter] = useState<Filter>(canUsers && canGroups ? 'all' : canUsers ? 'users' : 'groups');
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState<AdUser[]>([]);
  const [groups, setGroups] = useState<AdGroup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  // Per-entity failure so the error message reflects only what the filter shows.
  const [usersError, setUsersError] = useState(false);
  const [groupsError, setGroupsError] = useState(false);

  const showUsers = canUsers && filter !== 'groups';
  const showGroups = canGroups && filter !== 'users';

  const debouncedQuery = useDebouncedValue(query, DEBOUNCE_MS);
  const trimmed = debouncedQuery.trim();
  const hasQuery = trimmed.length >= MIN_QUERY_LENGTH;

  // Monotonic request counter: a response is applied only if its seq is still the
  // latest, discarding out-of-order/stale responses. Bumping it also invalidates
  // any in-flight request.
  const latestSeq = useRef(0);

  useEffect(() => {
    if (!hasQuery) {
      latestSeq.current += 1;
      setUsers([]);
      setGroups([]);
      setIsLoading(false);
      setUsersError(false);
      setGroupsError(false);
      return;
    }

    const seq = ++latestSeq.current;
    setIsLoading(true);

    (async () => {
      // Fetch both entity types the component can invite (not just the filtered
      // one, so toggling the filter needs no refetch), settling independently so
      // one type's failure doesn't discard the other's results.
      const [usersRes, groupsRes] = await Promise.allSettled([
        canUsers ? searchAdUsers(trimmed) : Promise.resolve<AdUser[]>([]),
        canGroups ? searchAdGroups(trimmed) : Promise.resolve<AdGroup[]>([]),
      ]);
      if (seq !== latestSeq.current) return;

      if (usersRes.status === 'rejected') console.error('Directory user search failed:', usersRes.reason);
      if (groupsRes.status === 'rejected') console.error('Directory group search failed:', groupsRes.reason);

      setUsers(usersRes.status === 'fulfilled' ? usersRes.value : []);
      setGroups(groupsRes.status === 'fulfilled' ? groupsRes.value : []);
      setUsersError(usersRes.status === 'rejected');
      setGroupsError(groupsRes.status === 'rejected');
      setIsLoading(false);
    })();
  }, [trimmed, hasQuery, canUsers, canGroups]);

  const handleFilterChange = (next: Filter) => setFilter(next);

  // Split fetched users into already-granted (dropped from results, surfaced by
  // the parent) and the rest (still invitable here).
  const { newUsers, matchedExistingIds } = useMemo(() => {
    const fresh: AdUser[] = [];
    const matched: string[] = [];
    for (const u of users) {
      if (u.mail && existingUserIds?.has(u.mail.toLowerCase())) matched.push(u.mail);
      else fresh.push(u);
    }
    return { newUsers: fresh, matchedExistingIds: matched };
  }, [users, existingUserIds]);

  const { newGroups, matchedExistingGroupIds } = useMemo(() => {
    const fresh: AdGroup[] = [];
    const matched: string[] = [];
    for (const g of groups) {
      if (existingGroupIds?.has(g.distinguishedName.toLowerCase())) matched.push(g.distinguishedName);
      else fresh.push(g);
    }
    return { newGroups: fresh, matchedExistingGroupIds: matched };
  }, [groups, existingGroupIds]);

  // Key the effect on the id contents (not array identity) so it fires only when
  // the matched set actually changes.
  const matchedUserKey = (showUsers ? matchedExistingIds : []).join('\n');
  useEffect(() => {
    onExistingUsersMatched?.(matchedUserKey ? matchedUserKey.split('\n') : []);
  }, [matchedUserKey, onExistingUsersMatched]);

  const matchedGroupKey = (showGroups ? matchedExistingGroupIds : []).join('\n');
  useEffect(() => {
    onExistingGroupsMatched?.(matchedGroupKey ? matchedGroupKey.split('\n') : []);
  }, [matchedGroupKey, onExistingGroupsMatched]);

  const placeholder = useMemo(() => {
    if (canUsers && canGroups) return t('admin.searchPlaceholder', 'Search users & groups by name or email…');
    if (canGroups) return t('admin.searchGroupsPlaceholder', 'Search groups by name or email…');
    return t('admin.searchUsersPlaceholder', 'Search users by name or email…');
  }, [canUsers, canGroups, t]);

  const visibleUsers = showUsers ? newUsers : [];
  const visibleGroups = showGroups ? newGroups : [];
  const isEmpty = visibleUsers.length === 0 && visibleGroups.length === 0;
  // Error only when every shown entity type failed.
  const error =
    (!showUsers || usersError) && (!showGroups || groupsError);

  return (
    <div>
      {canUsers && canGroups && (
        <div className="flex items-center gap-1 p-0.5 mb-2 bg-muted/40 rounded-md w-fit">
          <FilterButton
            active={filter === 'all'}
            onClick={() => handleFilterChange('all')}
            label={t('admin.searchAll', 'All')}
          />
          <FilterButton
            active={filter === 'users'}
            onClick={() => handleFilterChange('users')}
            icon={<User size={14} />}
            label={t('admin.searchUsers', 'Users')}
          />
          <FilterButton
            active={filter === 'groups'}
            onClick={() => handleFilterChange('groups')}
            icon={<Users size={14} />}
            label={t('admin.searchGroups', 'Groups')}
          />
        </div>
      )}

      <div className="relative">
        <Search
          size={14}
          className="absolute start-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
        />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="ps-8"
        />
      </div>

      {/* Fixed-height region so the modal doesn't jump as loading/empty states swap in. */}
      <div className="mt-2 h-[200px] overflow-auto">
        {!hasQuery ? (
          <StateMessage>{t('admin.searchMinChars', 'Type at least 3 characters to search')}</StateMessage>
        ) : isLoading ? (
          <StateMessage><LoadingDots /></StateMessage>
        ) : error ? (
          <StateMessage tone="error">{t('admin.searchUnavailable', 'Directory search is unavailable')}</StateMessage>
        ) : isEmpty ? (
          <StateMessage>{t('admin.searchNoResults', 'No results')}</StateMessage>
        ) : (
          <div className="space-y-0.5">
            {showUsers &&
              newUsers.map((u) => (
                <ResultRow
                  key={`u:${u.distinguishedName}`}
                  icon={<User size={14} className="shrink-0 text-muted-foreground" />}
                  title={u.displayName}
                  subtitle={u.mail || t('admin.searchNoEmail', 'No email — cannot invite')}
                  inviteLabel={t('admin.searchInvite', 'Invite')}
                  onInvite={() => onInviteUser?.(u)}
                  canInvite={!!u.mail}
                />
              ))}
            {showGroups &&
              newGroups.map((g) => (
                <ResultRow
                  key={`g:${g.distinguishedName}`}
                  icon={<Users size={14} className="shrink-0 text-muted-foreground" />}
                  title={g.displayName}
                  subtitle={g.mail}
                  inviteLabel={t('admin.searchInvite', 'Invite')}
                  onInvite={() => onInviteGroup?.(g)}
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StateMessage({ children, tone = 'muted' }: { children: React.ReactNode; tone?: 'muted' | 'error' }) {
  return (
    <div className="h-full flex items-center justify-center">
      <p className={`text-xs text-center ${tone === 'error' ? 'text-destructive' : 'text-muted-foreground'}`}>
        {children}
      </p>
    </div>
  );
}

function ResultRow({
  icon,
  title,
  subtitle,
  inviteLabel,
  onInvite,
  canInvite = true,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  inviteLabel: string;
  onInvite: () => void;
  canInvite?: boolean;
}) {
  return (
    <div className="group flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/40 transition-colors">
      {icon}
      <span className="flex-1 min-w-0">
        <span className="block text-[13px] truncate">{title}</span>
        {subtitle && <span className="block text-xs text-muted-foreground truncate">{subtitle}</span>}
      </span>
      {canInvite && (
        <Button
          size="sm"
          variant="ghost"
          onClick={onInvite}
          aria-label={inviteLabel}
          className="shrink-0 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
        >
          <UserPlus size={14} className="mr-1" />
          {inviteLabel}
        </Button>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[13px] transition-colors ${
        active
          ? 'bg-primary text-primary-foreground font-medium shadow-[var(--shadow-sm)]'
          : 'text-muted-foreground hover:text-foreground hover:bg-background/60'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
