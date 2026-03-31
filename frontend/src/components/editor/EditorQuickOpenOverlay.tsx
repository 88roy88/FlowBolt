import type { RefObject } from 'react';
import type { TFunction } from 'i18next';
import { getBaseName } from './editorFilePaths';

type Props = {
  t: TFunction;
  quickOpenInputRef: RefObject<HTMLInputElement | null>;
  quickOpenQuery: string;
  onQuickOpenQueryChange: (value: string) => void;
  onQuickOpenKeyDown: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  quickOpenResults: string[];
  quickOpenSelectedIndex: number;
  onQuickOpenSelectedIndexChange: (index: number | ((prev: number) => number)) => void;
  onDismiss: () => void;
  openQuickOpenFile: (path: string) => void;
};

export function EditorQuickOpenOverlay({
  t,
  quickOpenInputRef,
  quickOpenQuery,
  onQuickOpenQueryChange,
  onQuickOpenKeyDown,
  quickOpenResults,
  quickOpenSelectedIndex,
  onQuickOpenSelectedIndexChange,
  onDismiss,
  openQuickOpenFile,
}: Props) {
  return (
    <div
      onMouseDown={onDismiss}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 40,
        background: 'rgba(0, 0, 0, 0.15)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'center',
        paddingTop: 28,
      }}
    >
      <div
        onMouseDown={(e: React.MouseEvent) => e.stopPropagation()}
        style={{
          width: 'min(700px, calc(100% - 40px))',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 10,
          boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
          overflow: 'hidden',
        }}
      >
        <input
          ref={quickOpenInputRef}
          value={quickOpenQuery}
          onChange={(e) => {
            onQuickOpenQueryChange(e.target.value);
            onQuickOpenSelectedIndexChange(0);
          }}
          onKeyDown={onQuickOpenKeyDown}
          placeholder={t('editor.quickOpenPlaceholder')}
          style={{
            width: '100%',
            border: 'none',
            borderBottom: '1px solid var(--border)',
            outline: 'none',
            background: 'var(--surface)',
            color: 'var(--text)',
            padding: '10px 12px',
            fontSize: 14,
          }}
        />

        <div style={{ maxHeight: 320, overflow: 'auto' }}>
          {quickOpenResults.length === 0 ? (
            <div style={{ padding: 12, color: 'var(--text-dim)', fontSize: 13 }}>{t('editor.noMatchingFiles')}</div>
          ) : (
            quickOpenResults.map((path: string, idx: number) => {
              const isSelected = idx === quickOpenSelectedIndex;
              return (
                <button
                  key={path}
                  onMouseEnter={() => onQuickOpenSelectedIndexChange(idx)}
                  onMouseDown={(e: React.MouseEvent) => {
                    e.preventDefault();
                    openQuickOpenFile(path);
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    border: 'none',
                    borderBottom: '1px solid var(--border)',
                    background: isSelected ? 'var(--bg)' : 'transparent',
                    color: 'var(--text)',
                    padding: '8px 12px',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 2,
                  }}
                >
                  <span style={{ fontSize: 13 }}>{getBaseName(path)}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{path}</span>
                </button>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
