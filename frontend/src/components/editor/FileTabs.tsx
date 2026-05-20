import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { useFilesStore } from '../../stores/files';
import { X } from 'lucide-react';
import { flattenFileTreeEntries } from './editorFilePaths';
import { normalizePath } from './fileTreePaths';

export function FileTabs() {
  const { t } = useTranslation();
  const { openFiles, fileTree, activeFilePath, setActiveFile, closeFile } = useFilesStore();
  const paths = useMemo(() => Array.from(openFiles.keys()), [openFiles]);
  const existingPaths = useMemo(
    () => new Set(flattenFileTreeEntries(fileTree).map(normalizePath)),
    [fileTree]
  );

  if (paths.length === 0) return null;

  const normalizedActive = activeFilePath ? normalizePath(activeFilePath) : null;

  return (
    <div className="flex overflow-auto bg-surface border-b border-border shrink-0">
      {paths.map((path) => {
        const normalizedPath = normalizePath(path);
        const fileName = normalizedPath.split('/').pop() ?? normalizedPath;
        const isActive = normalizedPath === normalizedActive;
        const isMissing = !existingPaths.has(normalizedPath);
        return (
          <div
            key={normalizedPath}
            data-file-path={normalizedPath}
            data-missing={isMissing ? 'true' : 'false'}
            className={`group relative flex items-center gap-1.5 px-3 py-1.5 text-[13px] cursor-pointer whitespace-nowrap shrink-0 transition-colors duration-100 ${
              isActive
                ? 'bg-background text-foreground -mb-px border-b-2 border-b-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
            } ${isMissing ? 'text-destructive/80 bg-destructive/5' : ''}`}
            onClick={() => setActiveFile(normalizedPath)}
            onMouseDown={(e) => {
              if (e.button === 1) {
                e.preventDefault();
                closeFile(normalizedPath);
              }
            }}
          >
            <span className={isMissing ? 'line-through decoration-2' : ''} title={isMissing ? t('editor.deletedTab') : undefined}>
              {fileName}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeFile(normalizedPath);
              }}
              className="flex items-center p-0.5 rounded-sm text-muted-foreground opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity"
              title={t('editor.closeTab')}
            >
              <X size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
