import type { RefObject } from 'react';
import type { TFunction } from 'i18next';
import { ChevronRight } from 'lucide-react';
import type { SearchResult } from '../../services/api';

type Props = {
  t: TFunction;
  searchInputRef: RefObject<HTMLInputElement | null>;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  onSearchKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  performSearch: () => void;
  searchBusy: boolean;
  projectId: string | null;
  searchCaseSensitive: boolean;
  onSearchCaseSensitiveChange: (checked: boolean) => void;
  searchResults: SearchResult[];
  searchError: string | null;
  collapsedSearchFiles: Set<string>;
  toggleSearchFileCollapsed: (path: string) => void;
  jumpToSearchHit: (path: string, line: number, column: number) => void;
};

export function EditorSearchPanel({
  t,
  searchInputRef,
  searchQuery,
  onSearchQueryChange,
  onSearchKeyDown,
  performSearch,
  searchBusy,
  projectId,
  searchCaseSensitive,
  onSearchCaseSensitiveChange,
  searchResults,
  searchError,
  collapsedSearchFiles,
  toggleSearchFileCollapsed,
  jumpToSearchHit,
}: Props) {
  return (
    <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 10, flex: 1, overflow: 'hidden' }}>
      <input
        ref={searchInputRef}
        value={searchQuery}
        onChange={(e) => onSearchQueryChange(e.target.value)}
        onKeyDown={onSearchKeyDown}
        placeholder={t('editor.searchInFilesPlaceholder')}
        style={{
          width: '100%',
          background: 'var(--bg)',
          color: 'var(--text)',
          border: '1px solid var(--border)',
          borderRadius: 8,
          padding: '8px 10px',
          outline: 'none',
          fontSize: 13,
        }}
      />

      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button
          onClick={performSearch}
          disabled={searchBusy || !projectId}
          style={{
            padding: '7px 10px',
            borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'var(--bg)',
            cursor: searchBusy ? 'not-allowed' : 'pointer',
            color: 'var(--text)',
            opacity: searchBusy ? 0.6 : 1,
            whiteSpace: 'nowrap',
            fontSize: 12,
          }}
          title={t('editor.runSearch')}
        >
          {searchBusy ? t('editor.searching') : t('editor.runSearch')}
        </button>

        <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 12, color: 'var(--text-dim)' }}>
          <input
            type="checkbox"
            checked={searchCaseSensitive}
            onChange={(e) => onSearchCaseSensitiveChange(e.target.checked)}
          />
          {t('editor.caseSensitive')}
        </label>

        <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-dim)' }}>
          {searchResults.length
            ? t('editor.matchesCount', {
                count: searchResults.reduce((a: number, r: SearchResult) => a + r.hits.length, 0),
              })
            : ' '}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
        {searchBusy ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13 }}>{t('editor.searching')}</div>
        ) : searchError ? (
          <div style={{ color: 'var(--danger)', fontSize: 13, padding: '8px 0' }}>
            {t('editor.searchFailedPrefix')}: {searchError}
          </div>
        ) : searchResults.length === 0 ? (
          <div style={{ color: 'var(--text-dim)', fontSize: 13, padding: '8px 0' }}>{t('editor.noSearchResults')}</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {searchResults.map((r: SearchResult) => (
              <div key={r.path} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10 }}>
                {(() => {
                  const isCollapsed = collapsedSearchFiles.has(r.path);
                  return (
                    <>
                      <button
                        onClick={() => toggleSearchFileCollapsed(r.path)}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          fontSize: 12,
                          color: 'var(--text-dim)',
                          marginBottom: isCollapsed ? 0 : 8,
                          background: 'transparent',
                          border: 'none',
                          cursor: 'pointer',
                          padding: 0,
                          textAlign: 'left',
                        }}
                        title={isCollapsed ? t('editor.showMatches') : t('editor.hideMatches')}
                      >
                        <ChevronRight
                          size={13}
                          style={{ transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)', transition: 'transform 120ms ease' }}
                        />
                        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {r.path} ({r.hits.length})
                        </span>
                      </button>
                      {!isCollapsed && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                          {r.hits.map((h: { line: number; column: number; preview: string }, idx: number) => (
                            <button
                              key={`${r.path}:${h.line}:${h.column}:${idx}`}
                              onClick={() => {
                                jumpToSearchHit(r.path, h.line, h.column);
                              }}
                              style={{
                                textAlign: 'left',
                                padding: '6px 8px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: 'var(--bg)',
                                cursor: 'pointer',
                                color: 'var(--text)',
                                fontSize: 13,
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                              }}
                              title={t('editor.jumpToMatch')}
                            >
                              {h.line}:{h.column} {h.preview}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
