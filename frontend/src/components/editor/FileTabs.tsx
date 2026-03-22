import { useFilesStore } from '../../stores/files';
import { X } from 'lucide-react';

export function FileTabs() {
  const { openFiles, activeFilePath, setActiveFile, closeFile } = useFilesStore();
  const paths = Array.from(openFiles.keys());

  if (paths.length === 0) return null;

  return (
    <div className="flex overflow-auto bg-surface border-b border-border shrink-0">
      {paths.map((path) => {
        const fileName = path.split('/').pop() ?? path;
        const isActive = path === activeFilePath;
        return (
          <div
            key={path}
            className={`group relative flex items-center gap-1.5 px-3 py-1.5 text-[13px] cursor-pointer whitespace-nowrap shrink-0 transition-colors duration-100 ${
              isActive
                ? 'bg-background text-foreground -mb-px border-b-2 border-b-primary'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/30'
            }`}
            onClick={() => setActiveFile(path)}
            onMouseDown={(e) => {
              if (e.button === 1) {
                e.preventDefault();
                closeFile(path);
              }
            }}
          >
            <span>{fileName}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeFile(path);
              }}
              className="flex items-center p-0.5 rounded-sm text-muted-foreground opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity"
              title="Close"
            >
              <X size={12} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
