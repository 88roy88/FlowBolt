import type { TFunction } from 'i18next';
import { Search, Files } from 'lucide-react';

type LeftTab = 'files' | 'search';

type Props = {
  t: TFunction;
  leftTab: LeftTab;
  projectId: string | null;
  onShowFiles: () => void;
  onShowSearch: () => void;
  searchResultCount?: number;
};

export function EditorSidebarHeader({
  t,
  leftTab,
  projectId,
  onShowFiles,
  onShowSearch,
  searchResultCount = 0,
}: Props) {
  return (
    <div className="flex items-center gap-2 px-3 py-[7px] border-b border-border shrink-0 bg-card/50">
        {/* Tab Switcher */}
        <div className="flex gap-1 bg-muted/50 p-0.5 rounded-md">
          <button
            type="button"
            onClick={onShowFiles}
            disabled={!projectId}
            className={`
              flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium transition-all
              ${leftTab === 'files'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
              }
              ${!projectId ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
            `}
            title={t('editor.files')}
          >
            <Files size={12} />
            <span>{t('editor.files')}</span>
          </button>

          <button
            type="button"
            onClick={onShowSearch}
            disabled={!projectId}
            className={`
              relative flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium transition-all
              ${leftTab === 'search'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground hover:bg-background/50'
              }
              ${!projectId ? 'opacity-30 cursor-not-allowed' : 'cursor-pointer'}
            `}
            title={`${t('editor.searchShortcutTitle')} (⇧⌘F)`}
          >
            <Search size={12} />
            <span>{t('editor.searchTab')}</span>
            {searchResultCount > 0 && (
              <span
                className="
                  flex items-center justify-center min-w-[16px] h-[16px] px-1
                  text-[9px] font-bold rounded-full
                  bg-accent text-accent-foreground
                  shadow-sm
                "
              >
                {searchResultCount > 99 ? '99+' : searchResultCount}
              </span>
            )}
          </button>
        </div>
    </div>
  );
}
