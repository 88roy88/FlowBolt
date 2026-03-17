import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { Folder, FolderOpen, File } from 'lucide-react';
import { useState } from 'react';

interface TreeNodeProps {
  entry: FileEntry;
  depth: number;
}

function TreeNode({ entry, depth }: TreeNodeProps) {
  const { openFile, activeFilePath } = useFilesStore();
  const [expanded, setExpanded] = useState(depth < 2);

  const isActive = activeFilePath === entry.path;

  if (entry.is_directory) {
    return (
      <div>
        <div
          onClick={() => setExpanded((v) => !v)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-sm)',
            padding: 'var(--space-sm) var(--space-md)',
            paddingLeft: `${12 + depth * 16}px`,
            cursor: 'pointer',
            fontSize: '13px',
            color: 'var(--text)',
          }}
        >
          {expanded
            ? <FolderOpen size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            : <Folder size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
          }
          <span className="truncate">{entry.name}</span>
        </div>
        {expanded && entry.children?.map((child) => (
          <TreeNode key={child.path} entry={child} depth={depth + 1} />
        ))}
      </div>
    );
  }

  return (
    <div
      onClick={() => openFile(entry.path)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-sm)',
        padding: 'var(--space-sm) var(--space-md)',
        paddingLeft: `${12 + depth * 16}px`,
        cursor: 'pointer',
        fontSize: '13px',
        color: isActive ? 'var(--accent)' : 'var(--text)',
        background: isActive ? 'rgba(var(--accent-rgb), 0.12)' : 'transparent',
        borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
      }}
    >
      <File size={14} style={{ flexShrink: 0, color: 'var(--text-dim)' }} />
      <span className="truncate">{entry.name}</span>
    </div>
  );
}

export function FileTree() {
  const fileTree = useFilesStore((s) => s.fileTree);

  if (fileTree.length === 0) {
    return (
      <div style={{
        padding: 'var(--space-lg)',
        fontSize: '12px',
        color: 'var(--text-dim)',
        textAlign: 'center',
      }}>
        No files yet
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--space-sm) 0' }}>
      {fileTree.map((entry) => (
        <TreeNode key={entry.path} entry={entry} depth={0} />
      ))}
    </div>
  );
}
