import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { Folder, FolderOpen, File, FileJson, FileCode, FileText as FileTextIcon, Image, Settings, Plus, Pencil, Trash2, Upload } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { type ChangeEvent, useRef, useState } from 'react';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Button } from '../ui/button';

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
  onCreate: (basePath: string) => void;
  onUpload: (basePath: string) => void;
  onRename: (entry: FileEntry) => void;
  onDelete: (entry: FileEntry) => void;
  readOnly: boolean;
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

function TreeNode({ entry, depth, onCreate, onUpload, onRename, onDelete, readOnly }: TreeNodeProps) {
  const { t } = useTranslation();
  const { openFile, activeFilePath } = useFilesStore();
  const [expanded, setExpanded] = useState(depth < 2);
  const isActive = activeFilePath === entry.path;
  const createInBasePath = entry.is_directory ? entry.path : parentDirectory(entry.path);

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
          <TreeNode
            key={child.path}
            entry={child}
            depth={depth + 1}
            onCreate={onCreate}
            onUpload={onUpload}
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

type FileActionDialogState =
  | { mode: 'create'; basePath: string }
  | { mode: 'rename'; entry: FileEntry }
  | { mode: 'delete'; entry: FileEntry }
  | null;

interface FileTreeProps {
  readOnly: boolean;
  readOnlyMessage: string;
}

export function FileTree({ readOnly, readOnlyMessage }: FileTreeProps) {
  const { t } = useTranslation();
  const fileTree = useFilesStore((s) => s.fileTree);
  const createFile = useFilesStore((s) => s.createFile);
  const uploadFiles = useFilesStore((s) => s.uploadFiles);
  const renamePath = useFilesStore((s) => s.renamePath);
  const deletePath = useFilesStore((s) => s.deletePath);
  const [dialogState, setDialogState] = useState<FileActionDialogState>(null);
  const [inputValue, setInputValue] = useState('');
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploadBasePath, setUploadBasePath] = useState('/');

  const closeDialog = () => {
    setDialogState(null);
    setInputValue('');
    setDialogError(null);
    setIsSubmitting(false);
  };

  const openCreateDialog = (basePath: string) => {
    if (readOnly) return;
    setDialogState({ mode: 'create', basePath });
    setInputValue('');
    setDialogError(null);
  };

  const openRenameDialog = (entry: FileEntry) => {
    if (readOnly) return;
    setDialogState({ mode: 'rename', entry });
    setInputValue(entry.name);
    setDialogError(null);
  };

  const openDeleteDialog = (entry: FileEntry) => {
    if (readOnly) return;
    setDialogState({ mode: 'delete', entry });
    setInputValue('');
    setDialogError(null);
  };

  const openUploadDialog = (basePath: string) => {
    if (readOnly) return;
    setUploadBasePath(basePath);
    fileInputRef.current?.click();
  };

  const handleUploadSelection = async (event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files ? Array.from(event.target.files) : [];
    if (selectedFiles.length === 0) return;
    setDialogError(null);
    setIsSubmitting(true);
    try {
      await uploadFiles(uploadBasePath, selectedFiles);
    } catch (err) {
      console.error('Upload failed', err);
      setDialogError(t('editor.uploadFailed'));
    } finally {
      event.target.value = '';
      setIsSubmitting(false);
    }
  };

  const submitDialogAction = async () => {
    if (!dialogState) return;
    setDialogError(null);
    setIsSubmitting(true);
    try {
      if (dialogState.mode === 'create') {
        const nextName = inputValue.trim();
        if (!nextName) {
          setDialogError(t('editor.fileNameRequired'));
          return;
        }
        await createFile(joinPath(dialogState.basePath, nextName));
        closeDialog();
        return;
      }

      if (dialogState.mode === 'rename') {
        const nextName = inputValue.trim();
        if (!nextName) {
          setDialogError(t('editor.fileNameRequired'));
          return;
        }
        if (nextName === dialogState.entry.name) {
          closeDialog();
          return;
        }
        const nextPath = joinPath(parentDirectory(dialogState.entry.path), nextName);
        await renamePath(dialogState.entry.path, nextPath);
        closeDialog();
        return;
      }

      await deletePath(dialogState.entry.path);
      closeDialog();
    } catch (err) {
      console.error('File action failed', err);
      setDialogError(t('editor.fileActionFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDialogOpen = dialogState !== null;
  const isDeleteMode = dialogState?.mode === 'delete';
  const dialogTitle = dialogState?.mode === 'create'
    ? t('editor.createFile')
    : dialogState?.mode === 'rename'
      ? t('editor.renameFile')
      : t('editor.deleteFile');
  const dialogDescription = dialogState?.mode === 'delete'
    ? t('editor.confirmDeleteFile', { name: dialogState.entry.name })
    : undefined;

  if (fileTree.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 px-4 text-center">
        <div className="mb-1 grid w-full max-w-[260px] grid-cols-2 gap-1">
          <button
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
            onClick={() => openCreateDialog('/')}
            disabled={readOnly}
          >
            {t('editor.createFile')}
          </button>
          <button
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
            onClick={() => openUploadDialog('/')}
            disabled={readOnly}
          >
            {t('editor.uploadFiles')}
          </button>
        </div>
        {readOnly && (
          <span className="text-[11px] text-muted-foreground">{readOnlyMessage}</span>
        )}
        {!readOnly && dialogError && (
          <span className="text-[11px] text-destructive">{dialogError}</span>
        )}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          data-testid="file-upload-input"
          onChange={(e) => void handleUploadSelection(e)}
        />
        <Folder size={28} className="text-muted-foreground opacity-30" />
        <span className="text-xs text-muted-foreground">
          No files yet. Start a conversation to scaffold your project.
        </span>
      </div>
    );
  }

  return (
    <>
      <div className="py-1">
        <div className="grid grid-cols-2 gap-1 px-2 pb-1">
          <button
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
            onClick={() => openCreateDialog('/')}
            disabled={readOnly}
          >
            {t('editor.createFile')}
          </button>
          <button
            type="button"
            className="rounded border border-border bg-background px-2 py-1 text-[11px] hover:bg-muted"
            onClick={() => openUploadDialog('/')}
            disabled={readOnly}
          >
            {t('editor.uploadFiles')}
          </button>
        </div>
        {readOnly && (
          <div className="px-2 pb-2 text-[11px] text-muted-foreground">
            {readOnlyMessage}
          </div>
        )}
        {!readOnly && dialogError && (
          <div className="px-2 pb-2 text-[11px] text-destructive">
            {dialogError}
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          data-testid="file-upload-input"
          onChange={(e) => void handleUploadSelection(e)}
        />
        {fileTree.map((entry) => (
          <TreeNode
            key={entry.path}
            entry={entry}
            depth={0}
            onCreate={openCreateDialog}
            onUpload={openUploadDialog}
            onRename={openRenameDialog}
            onDelete={openDeleteDialog}
            readOnly={readOnly}
          />
        ))}
      </div>
      <Dialog open={isDialogOpen} onOpenChange={(open) => { if (!open) closeDialog(); }}>
        <DialogContent className="w-full max-w-[430px]">
          <DialogClose onClose={closeDialog} />
          <DialogTitle>{dialogTitle}</DialogTitle>
          {dialogDescription ? (
            <p className="mt-2 text-sm text-muted-foreground">{dialogDescription}</p>
          ) : (
            <div className="mt-3">
              <Input
                autoFocus
                value={inputValue}
                placeholder={dialogState?.mode === 'create' ? t('editor.newFilePrompt') : t('editor.renamePrompt')}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') void submitDialogAction();
                }}
              />
            </div>
          )}
          {dialogError && (
            <p className="mt-2 text-xs text-destructive">{dialogError}</p>
          )}
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={closeDialog} disabled={isSubmitting}>
              {t('common.cancel')}
            </Button>
            <Button
              variant={isDeleteMode ? 'destructive' : 'default'}
              onClick={() => void submitDialogAction()}
              disabled={isSubmitting}
            >
              {isDeleteMode ? t('common.delete') : dialogState?.mode === 'rename' ? t('common.save') : t('common.create')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
