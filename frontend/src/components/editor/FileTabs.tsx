import { useFilesStore } from '../../stores/files';
import { X } from 'lucide-react';

export function FileTabs() {
  const { openFiles, activeFilePath, setActiveFile, closeFile } = useFilesStore();
  const paths = Array.from(openFiles.keys());

  if (paths.length === 0) return null;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        overflow: 'auto',
        background: 'var(--surface)',
        minHeight: 40,
        padding: '8px 12px 10px',
        flexShrink: 0,
        boxShadow: 'var(--shadow-subtle)',
      }}
    >
      {paths.map((path) => {
        const fileName = path.split('/').pop() ?? path;
        const isActive = path === activeFilePath;
        return (
          <div
            key={path}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 10px 6px 12px',
              fontSize: '13px',
              cursor: 'pointer',
              background: isActive ? 'rgba(var(--accent-rgb), 0.18)' : 'transparent',
              color: isActive ? 'var(--text)' : 'var(--text-dim)',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              borderRadius: 'var(--radius-md)',
              boxShadow: isActive ? 'var(--shadow-soft)' : 'none',
              borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
              marginRight: 6,
            }}
            onClick={() => setActiveFile(path)}
          >
            <span>{fileName}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                closeFile(path);
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: 1,
                borderRadius: 3,
                color: 'var(--text-dim)',
                opacity: 0.6,
              }}
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
