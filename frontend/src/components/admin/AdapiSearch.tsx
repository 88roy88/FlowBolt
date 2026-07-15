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
  const [error, setError] = useState(false);

  const showUsers = canUsers && filter !== 'groups';
  const showGroups = canGroups && filter !== 'users';

  const debouncedQuery = useDebouncedValue(query, DEBOUNCE_MS);
  const trimmed = debouncedQuery.trim();
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_QUERY_LENGTH;
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
      setError(false);
      return;
    }

    const seq = ++latestSeq.current;
    setIsLoading(true);
    setError(false);

    (async () => {
      try {
        const [nextUsers, nextGroups] = await Promise.all([
          showUsers ? searchAdUsers(trimmed) : Promise.resolve([]),
          showGroups ? searchAdGroups(trimmed) : Promise.resolve([]),
        ]);
        if (seq === latestSeq.current) {
          setUsers(nextUsers);
          setGroups(nextGroups);
        }
      } catch (err) {
        console.error('ADAPI search failed:', err);
        if (seq === latestSeq.current) {
          setUsers([]);
          setGroups([]);
          setError(true);
        }
      } finally {
        if (seq === latestSeq.current) setIsLoading(false);
      }
    })();
  }, [trimmed, hasQuery, showUsers, showGroups]);

  const handleFilterChange = (next: Filter) => {
    if (next === filter) return;
    // Invalidate in-flight requests and drop results that fall out of scope.
    latestSeq.current += 1;
    setUsers([]);
    setGroups([]);
    setFilter(next);
  };

  const placeholder = useMemo(() => {
    if (canUsers && canGroups) return t('admin.searchPlaceholder', 'Search users & groups by name or email…');
    if (canGroups) return t('admin.searchGroupsPlaceholder', 'Search groups by name or email…');
    return t('admin.searchUsersPlaceholder', 'Search users by name or email…');
  }, [canUsers, canGroups, t]);

  const isEmpty = users.length === 0 && groups.length === 0;

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

      {/* Results */}
      <div className="mt-2 max-h-[360px] overflow-auto">
        {tooShort ? (
          <p className="text-muted-foreground text-xs text-center py-3">
            {t('admin.searchMinChars', 'Type at least 3 characters to search')}
          </p>
        ) : isLoading ? (
          <p className="text-muted-foreground text-xs text-center py-3">{t('common.loading', 'Loading...')}</p>
        ) : error ? (
          <p className="text-destructive text-xs text-center py-3">
            {t('admin.searchUnavailable', 'Directory search is unavailable')}
          </p>
        ) : !hasQuery ? null : isEmpty ? (
          <p className="text-muted-foreground text-xs text-center py-3">{t('admin.searchNoResults', 'No results')}</p>
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
          ? 'bg-background text-foreground shadow-[var(--shadow-sm)]'
          : 'text-muted-foreground hover:text-foreground'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
