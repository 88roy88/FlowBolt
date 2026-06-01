import { Folder, FolderOpen, Pencil, Plus, Trash2, Upload } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';
import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { getFileIcon } from './fileTreeIcons';
import { parentDirectory } from './fileTreePaths';

interface FileTreeNodeProps {
  entry: FileEntry;
  depth: number;
  onCreate: (basePath: string) => void;
  onUpload: (basePath: string) => void;
  onDropUpload: (basePath: string, files: File[]) => void;
  dropTargetPath: string | null;
  onDropTargetChange: (path: string | null) => void;
  onRename: (entry: FileEntry) => void;
  onDelete: (entry: FileEntry) => void;
  readOnly: boolean;
}

export function FileTreeNode({
  entry,
  depth,
  onCreate,
  onUpload,
  onDropUpload,
  dropTargetPath,
  onDropTargetChange,
  onRename,
  onDelete,
  readOnly,
}: FileTreeNodeProps) {
  const { t } = useTranslation();
  const { openFile, activeFilePath } = useFilesStore();
  const [expanded, setExpanded] = useState(depth < 2);
  const isActive = activeFilePath === entry.path;
  const createInBasePath = entry.is_directory ? entry.path : parentDirectory(entry.path);
  const isDropTarget = entry.is_directory && dropTargetPath === entry.path;

  if (entry.is_directory) {
    return (
      <div>
        <div
          onClick={() => setExpanded((v) => !v)}
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (readOnly) {
              e.dataTransfer.dropEffect = 'none';
              return;
            }
            e.dataTransfer.dropEffect = 'copy';
            onDropTargetChange(entry.path);
          }}
          onDragLeave={() => {
            if (dropTargetPath === entry.path) onDropTargetChange(null);
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            if (readOnly) return;
            const files = Array.from(e.dataTransfer.files ?? []);
            onDropTargetChange(null);
            if (files.length === 0) return;
            setExpanded(true);
            onDropUpload(createInBasePath, files);
          }}
          className={`group flex items-center gap-1 py-[3px] px-2 cursor-pointer text-[13px] truncate transition-colors duration-75 hover:bg-muted/40 ${
            isDropTarget ? 'bg-primary/10 ring-1 ring-primary/30' : ''
          }`}
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
                if (readOnly) return;
                onCreate(createInBasePath);
              }}
              title={t('editor.createFile')}
              disabled={readOnly}
            >
              <Plus size={12} />
            </button>
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation();
                if (readOnly) return;
                onUpload(createInBasePath);
              }}
              title={t('editor.uploadFiles')}
              disabled={readOnly}
            >
              <Upload size={12} />
            </button>
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted"
              onClick={(e) => {
                e.stopPropagation();
                if (readOnly) return;
                onRename(entry);
              }}
              title={t('editor.renameFile')}
              disabled={readOnly}
            >
              <Pencil size={12} />
            </button>
            <button
              type="button"
              className="rounded p-0.5 hover:bg-muted text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                if (readOnly) return;
                onDelete(entry);
              }}
              title={t('editor.deleteFile')}
              disabled={readOnly}
            >
              <Trash2 size={12} />
            </button>
          </div>
        </div>
        {expanded && entry.children?.map((child) => (
          <FileTreeNode
            key={child.path}
            entry={child}
            depth={depth + 1}
            onCreate={onCreate}
            onUpload={onUpload}
            onDropUpload={onDropUpload}
            dropTargetPath={dropTargetPath}
            onDropTargetChange={onDropTargetChange}
            onRename={onRename}
            onDelete={onDelete}
            readOnly={readOnly}
          />
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
            if (readOnly) return;
            onRename(entry);
          }}
          title={t('editor.renameFile')}
          disabled={readOnly}
        >
          <Pencil size={12} />
        </button>
        <button
          type="button"
          className="rounded p-0.5 hover:bg-muted text-destructive"
          onClick={(e) => {
            e.stopPropagation();
            if (readOnly) return;
            onDelete(entry);
          }}
          title={t('editor.deleteFile')}
          disabled={readOnly}
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}
