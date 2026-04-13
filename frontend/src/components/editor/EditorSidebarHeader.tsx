import { useState, useRef, useEffect } from 'react';
import type { TFunction } from 'i18next';
import { Search, Files, Download, ChevronDown, FileCode } from 'lucide-react';
import { downloadZip, downloadSingleHtml } from '../../services/api';

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
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  const handleExportZip = () => {
    if (projectId) {
      downloadZip(projectId);
      setExportMenuOpen(false);
    }
  };

  const handleExportHtml = () => {
    if (projectId) {
      downloadSingleHtml(projectId);
      setExportMenuOpen(false);
    }
  };

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    if (exportMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [exportMenuOpen]);

  return (
    <div className="flex items-center justify-between gap-2 px-3 py-[7px] border-b border-border shrink-0 bg-card/50">
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

      {/* Export Dropdown */}
      <div className="relative ms-auto" ref={exportMenuRef}>
        <button
          data-testid="export-dropdown-toggle"
          type="button"
          disabled={!projectId}
          onClick={() => setExportMenuOpen(!exportMenuOpen)}
          className={`
            flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-all
            ${projectId
              ? 'text-muted-foreground hover:text-foreground hover:bg-muted cursor-pointer'
              : 'opacity-30 cursor-not-allowed text-muted-foreground'
            }
          `}
          title={t('editor.exportZip')}
        >
          <Download size={12} />
          <ChevronDown size={10} className={`transition-transform ${exportMenuOpen ? 'rotate-180' : ''}`} />
        </button>
        {exportMenuOpen && (
          <div className="absolute right-0 top-full mt-1 z-50 min-w-[160px] rounded-md border border-border bg-popover shadow-lg">
            <div className="p-1">
              <button
                data-testid="export-zip-button"
                onClick={handleExportZip}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-[11px] hover:bg-accent transition-colors text-left"
              >
                <Download size={12} className="text-muted-foreground" />
                <span>{t('editor.exportZip')}</span>
              </button>
              <button
                onClick={handleExportHtml}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-[11px] hover:bg-accent transition-colors text-left"
              >
                <FileCode size={12} className="text-muted-foreground" />
                <span>{t('editor.exportHtml')}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
