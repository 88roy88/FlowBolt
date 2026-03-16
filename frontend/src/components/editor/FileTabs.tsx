import { useFilesStore } from '../../stores/files';
import { X } from 'lucide-react';

export function FileTabs() {
  const { openFiles, activeFilePath, setActiveFile, closeFile } = useFilesStore();
  const paths = Array.from(openFiles.keys());

  if (paths.length === 0) return null;

  return (
    <div style={{
      display: 'flex',
      overflow: 'auto',
      background: 'var(--surface)',
      borderBottom: '1px solid var(--border)',
      flexShrink: 0,
    }}>
      {paths.map((path) => {
        const fileName = path.split('/').pop() ?? path;
        const isActive = path === activeFilePath;
        return (
          <div
            key={path}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              fontSize: '13px',
              cursor: 'pointer',
              borderRight: '1px solid var(--border)',
              background: isActive ? 'var(--bg)' : 'transparent',
              color: isActive ? 'var(--text)' : 'var(--text-dim)',
              whiteSpace: 'nowrap',
              flexShrink: 0,
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
                padding: '1px',
                borderRadius: '3px',
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
