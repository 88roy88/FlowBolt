import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { Folder, FolderOpen, File, FileJson, FileCode, FileText as FileTextIcon, Image, Settings } from 'lucide-react';
import { useState } from 'react';

function getFileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'json': return <FileJson size={14} className="shrink-0 text-[#c9a04a]" />;
    case 'ts': case 'tsx': return <FileCode size={14} className="shrink-0 text-[#5a9bcf]" />;
    case 'js': case 'jsx': return <FileCode size={14} className="shrink-0 text-[#c4b456]" />;
    case 'css': case 'scss': return <FileCode size={14} className="shrink-0 text-[#6b8fd4]" />;
    case 'html': return <FileCode size={14} className="shrink-0 text-[#c47a5a]" />;
    case 'md': return <FileTextIcon size={14} className="shrink-0 text-muted-foreground" />;
    case 'png': case 'jpg': case 'svg': case 'gif': return <Image size={14} className="shrink-0 text-[#7ab88a]" />;
    case 'toml': case 'yaml': case 'yml': return <Settings size={14} className="shrink-0 text-muted-foreground" />;
    default: return <File size={14} className="shrink-0 text-muted-foreground" />;
  }
}

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
          className="flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px] truncate transition-colors duration-75 hover:bg-muted/40"
          style={{ paddingInlineStart: `${8 + depth * 14}px` }}
        >
          {expanded
            ? <FolderOpen size={14} className="text-primary shrink-0" />
            : <Folder size={14} className="text-primary shrink-0" />
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
      className={`flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px] truncate transition-colors duration-75 hover:bg-muted/40 ${
        isActive ? 'bg-background text-primary' : ''
      }`}
      style={{ paddingInlineStart: `${8 + depth * 14}px` }}
    >
      {getFileIcon(entry.name)}
      <span className="truncate">{entry.name}</span>
    </div>
  );
}

export function FileTree() {
  const fileTree = useFilesStore((s) => s.fileTree);

  if (fileTree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 px-4 text-center">
        <Folder size={28} className="text-muted-foreground opacity-30" />
        <span className="text-xs text-muted-foreground">
          No files yet. Start a conversation to scaffold your project.
        </span>
      </div>
    );
  }

  return (
    <div className="py-1">
      {fileTree.map((entry) => (
        <TreeNode key={entry.path} entry={entry} depth={0} />
      ))}
    </div>
  );
}
