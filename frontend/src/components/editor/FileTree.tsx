import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { Folder, FolderOpen, File, FileJson, FileCode, FileText as FileTextIcon, Image, Settings, Plus, Pencil, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
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

function normalizePath(path: string): string {
  const normalized = path.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/\/$/, '');
  return normalized.startsWith('/') ? normalized : `/${normalized}`;
}

function parentDirectory(path: string): string {
  const normalized = normalizePath(path);
  const idx = normalized.lastIndexOf('/');
  if (idx <= 0) return '/';
  return normalized.slice(0, idx);
}

function joinPath(basePath: string, childName: string): string {
  const base = normalizePath(basePath);
  const trimmed = childName.trim().replace(/^\/+/, '').replace(/\/+$/, '');
  if (!trimmed) return base;
  return base === '/' ? `/${trimmed}` : `${base}/${trimmed}`;
}

function TreeNode({ entry, depth }: TreeNodeProps) {
  const { t } = useTranslation();
  const { openFile, activeFilePath, createFile, renamePath, deletePath } = useFilesStore();
  const [expanded, setExpanded] = useState(depth < 2);
  const isActive = activeFilePath === entry.path;
  const createInBasePath = entry.is_directory ? entry.path : parentDirectory(entry.path);

  const handleCreate = async () => {
    const name = window.prompt(t('editor.newFilePrompt'), '');
    if (!name) return;
    try {
      await createFile(joinPath(createInBasePath, name));
    } catch (err) {
      console.error('Failed to create file', err);
      window.alert(t('editor.fileActionFailed'));
    }
  };

  const handleRename = async () => {
    const nextName = window.prompt(t('editor.renamePrompt'), entry.name);
    if (!nextName || nextName === entry.name) return;
    const nextPath = joinPath(parentDirectory(entry.path), nextName);
    try {
      await renamePath(entry.path, nextPath);
    } catch (err) {
      console.error('Failed to rename path', err);
      window.alert(t('editor.fileActionFailed'));
    }
  };

  const handleDelete = async () => {
    if (!window.confirm(t('editor.confirmDeleteFile', { name: entry.name }))) return;
    try {
      await deletePath(entry.path);
    } catch (err) {
      console.error('Failed to delete path', err);
      window.alert(t('editor.fileActionFailed'));
    }
  };

  if (entry.is_directory) {
    return (
      <div>
        <div
          onClick={() => setExpanded((v) => !v)}
          className="group flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px] truncate transition-colors duration-75 hover:bg-muted/40"
          style={{ paddingInlineStart: `${8 + depth * 14}px` }}
        >
          {expanded
            ? <FolderOpen size={14} className="text-primary shrink-0" />
            : <Folder size={14} className="text-primary shrink-0" />
          }
          <span className="truncate flex-1 min-w-0">{entry.name}</span>
          <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation();
                void handleCreate();
              }}
              title={t('editor.createFile')}
            >
              <Plus size={12} />
            </button>
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation();
                void handleRename();
              }}
              title={t('editor.renameFile')}
            >
              <Pencil size={12} />
            </button>
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                void handleDelete();
              }}
              title={t('editor.deleteFile')}
            >
              <Trash2 size={12} />
            </button>
          </div>
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
      className={`group flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px] truncate transition-colors duration-75 hover:bg-muted/40 ${
        isActive ? 'bg-background text-primary' : ''
      }`}
      style={{ paddingInlineStart: `${8 + depth * 14}px` }}
    >
      {getFileIcon(entry.name)}
      <span className="truncate flex-1 min-w-0">{entry.name}</span>
      <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          className="rounded p-0.5 hover:bg-muted"
          onClick={(e) => {
            e.stopPropagation();
            void handleRename();
          }}
          title={t('editor.renameFile')}
        >
          <Pencil size={12} />
        </button>
        <button
          type="button"
          className="rounded p-0.5 hover:bg-muted text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            void handleDelete();
          }}
          title={t('editor.deleteFile')}
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}

export function FileTree() {
  const { t } = useTranslation();
  const fileTree = useFilesStore((s) => s.fileTree);
  const createFile = useFilesStore((s) => s.createFile);

  const handleCreateAtRoot = async () => {
    const name = window.prompt(t('editor.newFilePrompt'), '');
    if (!name) return;
    try {
      await createFile(joinPath('/', name));
    } catch (err) {
      console.error('Failed to create file', err);
      window.alert(t('editor.fileActionFailed'));
    }
  };

  if (fileTree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 px-4 text-center">
        <button
          type="button"
          className="mb-1 rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
          onClick={() => void handleCreateAtRoot()}
        >
          {t('editor.createFile')}
        </button>
        <Folder size={28} className="text-muted-foreground opacity-30" />
        <span className="text-xs text-muted-foreground">
          No files yet. Start a conversation to scaffold your project.
        </span>
      </div>
    );
  }

  return (
    <div className="py-1">
      <div className="px-2 pb-1">
        <button
          type="button"
          className="w-full rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
          onClick={() => void handleCreateAtRoot()}
        >
          {t('editor.createFile')}
        </button>
      </div>
      {fileTree.map((entry) => (
        <TreeNode key={entry.path} entry={entry} depth={0} />
      ))}
    </div>
  );
}
