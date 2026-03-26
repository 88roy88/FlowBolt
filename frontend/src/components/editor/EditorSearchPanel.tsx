import type { RefObject } from 'react';
import type { TFunction } from 'i18next';
import { ChevronRight, Search, X, Loader2, FileText, FileCode } from 'lucide-react';
import type { SearchResult } from '../../services/api';

function getFileIcon(path: string) {
  const ext = path.split('.').pop()?.toLowerCase();
  const codeExts = ['ts', 'tsx', 'js', 'jsx', 'py', 'java', 'cpp', 'c', 'go', 'rs'];
  return codeExts.includes(ext || '') ? FileCode : FileText;
}

function highlightMatch(text: string, query: string, caseSensitive: boolean): React.ReactNode {
  if (!query.trim()) return text;

  const parts: React.ReactNode[] = [];
  const searchText = caseSensitive ? text : text.toLowerCase();
  const searchQuery = caseSensitive ? query : query.toLowerCase();

  let lastIndex = 0;
  let index = searchText.indexOf(searchQuery);

  while (index !== -1) {
    // Add text before match
    if (index > lastIndex) {
      parts.push(text.substring(lastIndex, index));
    }
    // Add highlighted match
    parts.push(
      <mark
        key={`match-${index}`}
        style={{
          background: 'var(--accent)',
          color: 'var(--accent-foreground)',
          padding: '0 2px',
          borderRadius: 2,
          fontWeight: 600,
        }}
      >
        {text.substring(index, index + query.length)}
      </mark>
    );
    lastIndex = index + query.length;
    index = searchText.indexOf(searchQuery, lastIndex);
  }

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts;
}

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
  const totalMatches = searchResults.reduce((a: number, r: SearchResult) => a + r.hits.length, 0);

  return (
    <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 12, flex: 1, overflow: 'hidden' }}>
      {/* Search Input with Icons */}
      <div style={{ position: 'relative' }}>
        <Search
          size={14}
          style={{
            position: 'absolute',
            left: 10,
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--muted-foreground)',
            pointerEvents: 'none',
          }}
        />
        <input
          ref={searchInputRef}
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          onKeyDown={onSearchKeyDown}
          placeholder={t('editor.searchInFilesPlaceholder')}
          style={{
            width: '100%',
            background: 'var(--input)',
            color: 'var(--foreground)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '8px 32px 8px 32px',
            outline: 'none',
            fontSize: 13,
            transition: 'border-color 0.2s, box-shadow 0.2s',
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = 'var(--ring)';
            e.currentTarget.style.boxShadow = '0 0 0 1px var(--ring)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = 'var(--border)';
            e.currentTarget.style.boxShadow = 'none';
          }}
        />
        {searchBusy ? (
          <Loader2
            size={14}
            style={{
              position: 'absolute',
              right: 10,
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--muted-foreground)',
              animation: 'spin 1s linear infinite',
            }}
          />
        ) : searchQuery ? (
          <button
            onClick={() => onSearchQueryChange('')}
            style={{
              position: 'absolute',
              right: 8,
              top: '50%',
              transform: 'translateY(-50%)',
              background: 'transparent',
              border: 'none',
              padding: 4,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 3,
              color: 'var(--muted-foreground)',
              transition: 'color 0.2s, background 0.2s',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = 'var(--foreground)';
              e.currentTarget.style.background = 'var(--muted)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = 'var(--muted-foreground)';
              e.currentTarget.style.background = 'transparent';
            }}
            title={t('editor.clearSearch') || 'Clear'}
          >
            <X size={14} />
          </button>
        ) : null}
      </div>

      {/* Search Options & Stats */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <label
          style={{
            display: 'flex',
            gap: 6,
            alignItems: 'center',
            fontSize: 12,
            color: 'var(--muted-foreground)',
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: 4,
            transition: 'background 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--muted)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
          }}
        >
          <input
            type="checkbox"
            checked={searchCaseSensitive}
            onChange={(e) => onSearchCaseSensitiveChange(e.target.checked)}
            style={{ cursor: 'pointer' }}
          />
          <span>Aa</span>
          <span style={{ fontSize: 11 }}>{t('editor.caseSensitive')}</span>
        </label>

        {totalMatches > 0 && (
          <div
            style={{
              marginLeft: 'auto',
              fontSize: 11,
              color: 'var(--muted-foreground)',
              background: 'var(--muted)',
              padding: '4px 8px',
              borderRadius: 4,
              fontWeight: 500,
            }}
          >
            {totalMatches} {totalMatches === 1 ? 'result' : 'results'}
          </div>
        )}
      </div>

      {/* Results Area */}
      <div style={{ flex: 1, overflow: 'auto', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
        {searchBusy ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: 'var(--muted-foreground)',
              fontSize: 13,
              padding: 8,
            }}
          >
            <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
            <span>{t('editor.searching')}</span>
          </div>
        ) : searchError ? (
          <div
            style={{
              color: 'var(--destructive)',
              fontSize: 13,
              padding: 12,
              background: 'var(--destructive-foreground)',
              borderRadius: 6,
              border: '1px solid var(--destructive)',
            }}
          >
            {t('editor.searchFailedPrefix')}: {searchError}
          </div>
        ) : !searchQuery ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 12,
              padding: 32,
              color: 'var(--muted-foreground)',
              textAlign: 'center',
            }}
          >
            <Search size={32} strokeWidth={1.5} />
            <div style={{ fontSize: 13 }}>
              <div style={{ fontWeight: 500, marginBottom: 4 }}>Search across all files</div>
              <div style={{ fontSize: 11, opacity: 0.8 }}>Start typing to find matches in your project</div>
            </div>
          </div>
        ) : searchResults.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 8,
              padding: 32,
              color: 'var(--muted-foreground)',
              textAlign: 'center',
            }}
          >
            <FileText size={24} strokeWidth={1.5} />
            <div style={{ fontSize: 12 }}>{t('editor.noSearchResults')}</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {searchResults.map((r: SearchResult) => {
              const FileIcon = getFileIcon(r.path);
              const isCollapsed = collapsedSearchFiles.has(r.path);
              return (
                <div
                  key={r.path}
                  style={{
                    border: '1px solid var(--border)',
                    borderRadius: 6,
                    overflow: 'hidden',
                    background: 'var(--card)',
                  }}
                >
                  <button
                    onClick={() => toggleSearchFileCollapsed(r.path)}
                    style={{
                      width: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 12,
                      color: 'var(--foreground)',
                      background: 'var(--muted)',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '8px 10px',
                      textAlign: 'left',
                      transition: 'background 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'var(--accent)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'var(--muted)';
                    }}
                    title={isCollapsed ? t('editor.showMatches') : t('editor.hideMatches')}
                  >
                    <ChevronRight
                      size={12}
                      style={{
                        transform: isCollapsed ? 'rotate(0deg)' : 'rotate(90deg)',
                        transition: 'transform 150ms ease',
                        flexShrink: 0,
                      }}
                    />
                    <FileIcon size={13} style={{ flexShrink: 0, opacity: 0.7 }} />
                    <span
                      style={{
                        flex: 1,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        fontWeight: 500,
                      }}
                    >
                      {r.path.split('/').pop()}
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        color: 'var(--muted-foreground)',
                        background: 'var(--background)',
                        padding: '2px 6px',
                        borderRadius: 3,
                        fontWeight: 600,
                      }}
                    >
                      {r.hits.length}
                    </span>
                  </button>
                  {!isCollapsed && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {r.hits.map((h: { line: number; column: number; preview: string }, idx: number) => (
                        <button
                          key={`${r.path}:${h.line}:${h.column}:${idx}`}
                          onClick={() => {
                            jumpToSearchHit(r.path, h.line, h.column);
                          }}
                          style={{
                            textAlign: 'left',
                            padding: '6px 10px 6px 32px',
                            border: 'none',
                            borderTop: idx === 0 ? '1px solid var(--border)' : 'none',
                            background: 'var(--background)',
                            cursor: 'pointer',
                            color: 'var(--foreground)',
                            fontSize: 12,
                            transition: 'background 0.2s',
                            fontFamily: 'monospace',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'var(--muted)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'var(--background)';
                          }}
                          title={t('editor.jumpToMatch')}
                        >
                          <span style={{ color: 'var(--muted-foreground)', minWidth: 40, flexShrink: 0 }}>
                            {h.line}:{h.column}
                          </span>
                          <span
                            style={{
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              flex: 1,
                            }}
                          >
                            {highlightMatch(h.preview, searchQuery, searchCaseSensitive)}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
