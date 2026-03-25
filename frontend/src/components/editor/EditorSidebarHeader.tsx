import type { TFunction } from 'i18next';
import { Download, FileCode, Search, Files } from 'lucide-react';

type LeftTab = 'files' | 'search';

type Props = {
  t: TFunction;
  leftTab: LeftTab;
  projectId: string | null;
  onExportZip: () => void;
  onShowFiles: () => void;
  onShowSearch: () => void;
  onExportHtml: () => void;
};

export function EditorSidebarHeader({
  t,
  leftTab,
  projectId,
  onExportZip,
  onShowFiles,
  onShowSearch,
  onExportHtml,
}: Props) {
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-[7px] border-b border-border shrink-0">
      <span className="text-[13px] font-semibold tracking-tight truncate min-w-0">
        {leftTab === 'files' ? t('editor.files') : t('editor.searchTab')}
      </span>

      <div className="flex gap-1 shrink-0">
        <button
          type="button"
          title={t('editor.exportZip')}
          disabled={!projectId}
          onClick={onExportZip}
          className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
            projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
          }`}
        >
          <Download size={13} />
        </button>

        <button
          type="button"
          title={t('editor.files')}
          disabled={!projectId}
          onClick={onShowFiles}
          className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
            projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
          }`}
        >
          <Files size={13} />
        </button>

        <button
          type="button"
          title={t('editor.searchShortcutTitle')}
          disabled={!projectId}
          onClick={onShowSearch}
          className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
            projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
          }`}
        >
          <Search size={13} />
        </button>

        <button
          type="button"
          title={t('editor.exportHtml')}
          disabled={!projectId}
          onClick={onExportHtml}
          className={`flex items-center p-1 rounded text-muted-foreground transition-colors ${
            projectId ? 'hover:text-foreground hover:bg-muted/50 cursor-pointer' : 'opacity-30 cursor-not-allowed'
          }`}
        >
          <FileCode size={13} />
        </button>
      </div>
    </div>
  );
}
