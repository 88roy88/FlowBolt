import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { User, Users, Search, UserPlus } from 'lucide-react';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { useDebouncedValue } from '../../hooks/useDebounce';
import { searchAdUsers, searchAdGroups } from '../../services/api';
import type { AdUser, AdGroup } from '../../types';

type Filter = 'all' | 'users' | 'groups';

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 300;

interface AdapiSearchProps {
  /** Invite the picked user (via the row's hover button). Omit to hide user results. */
  onInviteUser?: (user: AdUser) => void;
  /** Invite the picked group (via the row's hover button). Omit to hide group results. */
  onInviteGroup?: (group: AdGroup) => void;
}

/**
 * Unified directory search over ADAPI users and groups. When both callbacks are
 * supplied it shows an All / Users / Groups filter and searches whichever the
 * filter selects; with a single callback it silently narrows to that entity type
 * (no filter chrome). Each row reveals an invite button on hover. Results match
 * on account name, display name or email.
 */
export function AdapiSearch({ onInviteUser, onInviteGroup }: AdapiSearchProps) {
  const { t } = useTranslation();
  const canUsers = !!onInviteUser;
  const canGroups = !!onInviteGroup;

  // Filter defaults to the broadest actionable scope. With one capability there
  // is nothing to filter, so we pin the filter and hide the toggle.
  const [filter, setFilter] = useState<Filter>(canUsers && canGroups ? 'all' : canUsers ? 'users' : 'groups');
  const [query, setQuery] = useState('');
  const [users, setUsers] = useState<AdUser[]>([]);
  const [groups, setGroups] = useState<AdGroup[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  // Per-entity failure, tracked separately so the error message can reflect only
  // what the current filter actually shows (see `error` below).
  const [usersError, setUsersError] = useState(false);
  const [groupsError, setGroupsError] = useState(false);

  const showUsers = canUsers && filter !== 'groups';
  const showGroups = canGroups && filter !== 'users';

  const debouncedQuery = useDebouncedValue(query, DEBOUNCE_MS);
  const trimmed = debouncedQuery.trim();
  const hasQuery = trimmed.length >= MIN_QUERY_LENGTH;

  // Monotonic request counter. Every fired request captures a seq number; when a
  // response resolves we only apply it if it is still the latest one. This
  // discards out-of-order/stale responses (a slow earlier request landing after
  // a faster later one) — the "only show the last request" guard, sans RxJS.
  const latestSeq = useRef(0);

  useEffect(() => {
    // Below the threshold (including empty): clear everything, fire nothing.
    // Bumping the seq also invalidates any in-flight request.
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
      // Fetch every entity type the component can invite (canUsers/canGroups),
      // not just the ones the current filter shows — the filter is a display
      // toggle, so switching All → Users must not require a refetch. Each
      // endpoint settles independently: in 'all' mode one type having no matches
      // (which real ADAPI surfaces as an error, not an empty list) must not
      // discard the other type's results.
      const [usersRes, groupsRes] = await Promise.allSettled([
        canUsers ? searchAdUsers(trimmed) : Promise.resolve<AdUser[]>([]),
        canGroups ? searchAdGroups(trimmed) : Promise.resolve<AdGroup[]>([]),
      ]);
      if (seq !== latestSeq.current) return;

      if (usersRes.status === 'rejected') console.error('ADAPI user search failed:', usersRes.reason);
      if (groupsRes.status === 'rejected') console.error('ADAPI group search failed:', groupsRes.reason);

      setUsers(usersRes.status === 'fulfilled' ? usersRes.value : []);
      setGroups(groupsRes.status === 'fulfilled' ? groupsRes.value : []);
      setUsersError(usersRes.status === 'rejected');
      setGroupsError(groupsRes.status === 'rejected');
      setIsLoading(false);
    })();
  }, [trimmed, hasQuery, canUsers, canGroups]);

  // The filter only changes which already-fetched results are displayed, so no
  // refetch or result-clearing is needed.
  const handleFilterChange = (next: Filter) => setFilter(next);

  const placeholder = useMemo(() => {
    if (canUsers && canGroups) return t('admin.searchPlaceholder', 'Search users & groups by name or email…');
    if (canGroups) return t('admin.searchGroupsPlaceholder', 'Search groups by name or email…');
    return t('admin.searchUsersPlaceholder', 'Search users by name or email…');
  }, [canUsers, canGroups, t]);

  // Only the results the current filter displays count toward "empty"/"error".
  const visibleUsers = showUsers ? users : [];
  const visibleGroups = showGroups ? groups : [];
  const isEmpty = visibleUsers.length === 0 && visibleGroups.length === 0;
  // Error only when every entity type currently shown failed. If either shown
  // type succeeded (even with no matches), we show results rather than an error.
  const error =
    (!showUsers || usersError) && (!showGroups || groupsError);

  return (
    <div>
      {/* All / Users / Groups filter — only when both entity types are actionable */}
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

      {/* Search input */}
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

      {/* Results — a fixed-height region reserved from the start so the modal
          doesn't jump in height as results, loading and empty states swap in. */}
      <div className="mt-2 h-[300px] overflow-auto">
        {!hasQuery ? (
          <StateMessage>{t('admin.searchMinChars', 'Type at least 3 characters to search')}</StateMessage>
        ) : isLoading ? (
          <StateMessage>{t('common.loading', 'Loading...')}</StateMessage>
        ) : error ? (
          <StateMessage tone="error">{t('admin.searchUnavailable', 'Directory search is unavailable')}</StateMessage>
        ) : isEmpty ? (
          <StateMessage>{t('admin.searchNoResults', 'No results')}</StateMessage>
        ) : (
          <div className="space-y-0.5">
            {showUsers &&
              users.map((u) => (
                <ResultRow
                  key={`u:${u.distinguishedName}`}
                  icon={<User size={14} className="shrink-0 text-muted-foreground" />}
                  title={u.displayName}
                  subtitle={u.mail}
                  inviteLabel={t('admin.searchInvite', 'Invite')}
                  onInvite={() => onInviteUser?.(u)}
                />
              ))}
            {showGroups &&
              groups.map((g) => (
                <ResultRow
                  key={`g:${g.distinguishedName}`}
                  icon={<Users size={14} className="shrink-0 text-muted-foreground" />}
                  title={g.displayName}
                  subtitle={g.description || g.mail}
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

/** Centered placeholder (hint / loading / empty / error) filling the fixed-height results region. */
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
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  inviteLabel: string;
  onInvite: () => void;
}) {
  return (
    <div className="group flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-muted/40 transition-colors">
      {icon}
      <span className="flex-1 min-w-0">
        <span className="block text-[13px] truncate">{title}</span>
        {subtitle && <span className="block text-xs text-muted-foreground truncate">{subtitle}</span>}
      </span>
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
