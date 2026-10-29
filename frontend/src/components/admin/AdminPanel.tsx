import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Trash2, User, Users, ExternalLink, ArrowUp, ArrowDown } from 'lucide-react';
import { Dialog, DialogContent, DialogClose, DialogTitle } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { LoadingDots } from '../ui/loading-dots';
import { DirectorySearch } from './DirectorySearch';
import { cn } from '@/lib/utils';
import type { PlatformGroup, PlatformUser } from '../../types';
import * as api from '../../services/api';

// Rows whose id is in `hits` sort first; ties preserve order under a stable sort.
function rankHit(hits: Set<string>, a: string, b: string): number {
  const aHit = hits.has(a.toLowerCase());
  const bHit = hits.has(b.toLowerCase());
  return aHit === bHit ? 0 : aHit ? -1 : 1;
}

type Tab = 'users' | 'published';

type SortKey = 'name' | 'owner_id' | 'project_url' | 'created_at' | 'published_at';
type SortDir = 'asc' | 'desc';

const INITIAL_SORT_DIR: Record<SortKey, SortDir> = {
  name: 'asc',
  owner_id: 'asc',
  project_url: 'asc',
  created_at: 'desc',
  published_at: 'desc',
};

const APPS_GRID ='grid grid-cols-[1fr_130px_150px_80px_80px] gap-2';

/** Date only, with the full date + time of day on hover. */
function Timestamp({ iso }: { iso: string }) {
  const date = new Date(iso);
  return (
    <span className="text-muted-foreground text-xs cursor-default" title={date.toLocaleString()}>
      {date.toLocaleDateString()}
    </span>
  );
}

export function AdminPanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>('users');
  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [groups, setGroups] = useState<PlatformGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [highlightedUserIds, setHighlightedUserIds] = useState<string[]>([]);
  const [highlightedGroupIds, setHighlightedGroupIds] = useState<string[]>([]);

  // Lowercased for case-insensitive matching: stored user_id comes from the token
  // UniqueID claim, whose casing can differ from the directory-derived uniqueId.
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

  // Lazy: only hit the endpoint once the tab is actually opened.
  const appsQuery = useQuery({
    queryKey: ['admin', 'published-apps'],
    queryFn: api.fetchPublishedApps,
    enabled: tab === 'published',
  });
  const appsData = appsQuery.data;
  const apps = useMemo(() => appsData ?? [], [appsData]);
  const [appsSearch, setAppsSearch] = useState('');
  const [appsSort, setAppsSort] = useState<{ key: SortKey; dir: SortDir }>({ key: 'published_at', dir: 'desc' });

  const visibleApps = useMemo(() => {
    const query = appsSearch.trim().toLowerCase();
    const matchingApps = apps.filter((app) =>
      [app.name, app.owner_id, app.project_url].some((field) => field.toLowerCase().includes(query)));

    return matchingApps.sort((a, b) => {
      const order = a[appsSort.key].localeCompare(b[appsSort.key], undefined, { sensitivity: 'base' });
      return appsSort.dir === 'asc' ? order : -order;
    });
  }, [apps, appsSearch, appsSort]);

  const toggleSort = (key: SortKey) => setAppsSort((prev) => (prev.key === key
    ? { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    : { key, dir: INITIAL_SORT_DIR[key] }));

  const sortHeader = (key: SortKey, label: string) => {
    const active = appsSort.key === key;
    const SortIcon = appsSort.dir === 'asc' ? ArrowUp : ArrowDown;
    return (
      <button
        type="button"
        onClick={() => toggleSort(key)}
        className={cn('flex items-center gap-0.5 text-start hover:text-foreground', active && 'text-foreground')}
      >
        {label}
        {active && <SortIcon size={11} className="shrink-0" />}
      </button>
    );
  };

  const handleInviteUser = async (userId: string, displayName: string) => {
    setError('');
    try {
      const user = await api.invitePlatformUser(userId, displayName);
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

  const tabButton = (value: Tab, label: string) => (
    <button
      type="button"
      onClick={() => { setTab(value); setError(''); }}
      className={cn(
        'text-[13px] pb-1.5 border-b-2 transition-colors',
        tab === value
          ? 'border-primary text-foreground'
          : 'border-transparent text-muted-foreground hover:text-foreground',
      )}
    >
      {label}
    </button>
  );

  return (
    <Dialog open onOpenChange={() => onClose()}>
      <DialogContent
        className={cn(
          'max-h-[85vh] flex flex-col overflow-hidden',
          tab === 'published' ? 'w-[760px] max-w-[760px]' : 'w-[440px]',
        )}
      >
        <DialogClose onClose={onClose} />

        <div className="shrink-0">
          <DialogTitle className="mb-3">{t('admin.title', 'Admin')}</DialogTitle>

          {/* Tabs */}
          <div className="flex gap-4 mb-3 border-b border-border">
            {tabButton('users', t('admin.usersTab', 'Platform Users'))}
            {tabButton('published', t('admin.publishedTab', 'Published Apps'))}
          </div>

          {tab === 'users' && (
            <DirectorySearch
              onInviteUser={(u) => handleInviteUser(u.uniqueId, u.displayName)}
              onInviteGroup={(g) => handleInviteGroup(g.distinguishedName, g.displayName, g.mail)}
              existingUserIds={memberIds}
              onExistingUsersMatched={setHighlightedUserIds}
              existingGroupIds={groupIds}
              onExistingGroupsMatched={setHighlightedGroupIds}
            />
          )}

          {tab === 'published' && apps.length > 0 && (
            <Input
              placeholder={t('admin.searchApps', 'Search by project, owner or URL')}
              value={appsSearch}
              onChange={(e) => setAppsSearch(e.target.value)}
            />
          )}

          {(error || (tab === 'published' && appsQuery.isError)) && (
            <p className="text-destructive text-xs mt-2">{error || 'Failed to load published apps'}</p>
          )}

          {tab === 'published' && apps.length > 0 && (
            <div className={cn(APPS_GRID, 'px-2 pt-3 text-[11px] text-muted-foreground')}>
              {sortHeader('name', t('admin.colName', 'Project'))}
              {sortHeader('owner_id', t('admin.colOwner', 'Owner'))}
              {sortHeader('project_url', t('admin.colUrl', 'URL'))}
              {sortHeader('created_at', t('admin.colCreated', 'Created'))}
              {sortHeader('published_at', t('admin.colPublished', 'Published'))}
            </div>
          )}
        </div>

        {/* min-h-0 lets this scroll within the dialog's max-height instead of overflowing. */}
        <div className="border-t border-border mt-3 pt-3 flex-auto min-h-0 overflow-auto space-y-1">
          {tab === 'users' ? (
            loading ? (
              <p className="text-muted-foreground text-xs text-center py-4"><LoadingDots /></p>
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
            )
          ) : appsQuery.isLoading ? (
            <p className="text-muted-foreground text-xs text-center py-4"><LoadingDots /></p>
          ) : apps.length === 0 ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noPublished', 'No published apps yet')}</p>
          ) : visibleApps.length === 0 ? (
            <p className="text-muted-foreground text-xs text-center py-4">{t('admin.noMatches', 'No matching apps')}</p>
          ) : (
            visibleApps.map((a) => (
              <div
                key={a.project_id}
                className={cn(APPS_GRID, 'items-center px-2 py-1.5 rounded-md hover:bg-muted/30 group')}
              >
                {/* The hashchange listener in App selects the project; admins' project list includes every project. */}
                <button
                  type="button"
                  onClick={() => { window.location.hash = `#/project/${a.project_id}`; onClose(); }}
                  className="min-w-0 text-[13px] truncate text-start hover:underline"
                  title={`${t('admin.openProject', 'Open project')} (${a.project_id})`}
                >
                  {a.name}
                </button>
                <span className="text-muted-foreground text-xs text-left truncate" title={a.owner_id}>
                  {a.owner_id}
                </span>
                <a
                  href={a.public_path}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-primary hover:underline min-w-0"
                >
                  <span className="truncate">{a.project_url}</span>
                  <ExternalLink size={11} className="shrink-0" />
                </a>
                <Timestamp iso={a.created_at} />
                <Timestamp iso={a.published_at} />
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
