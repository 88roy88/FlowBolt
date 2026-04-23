import { useFilesStore } from '../../stores/files';
import type { FileEntry } from '../../types';
import { Folder } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { type ChangeEvent, type DragEvent, useRef, useState } from 'react';
import { FileTreeActionDialog, type FileActionDialogState } from './FileTreeActionDialog';
import { FileTreeNode } from './FileTreeNode';
import { joinPath, parentDirectory, ROOT_DROP_PATH } from './fileTreePaths';

interface FileTreeProps {
  readOnly: boolean;
  readOnlyMessage: string;
}

export function FileTree({ readOnly, readOnlyMessage }: FileTreeProps) {
  const { t, i18n } = useTranslation();
  const isRtl = i18n.dir(i18n.resolvedLanguage) === 'rtl';
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
  const [dropTargetPath, setDropTargetPath] = useState<string | null>(null);
  const isRootDropTarget = dropTargetPath === ROOT_DROP_PATH;

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

  const handleDropUpload = async (basePath: string, files: File[]) => {
    if (readOnly || files.length === 0) return;
    setDialogError(null);
    setIsSubmitting(true);
    try {
      await uploadFiles(basePath, files);
    } catch (err) {
      console.error('Upload failed', err);
      setDialogError(t('editor.uploadFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRootDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (readOnly) {
      event.dataTransfer.dropEffect = 'none';
      return;
    }
    event.dataTransfer.dropEffect = 'copy';
    setDropTargetPath(ROOT_DROP_PATH);
  };

  const handleRootDragLeave = (event: DragEvent<HTMLDivElement>) => {
    const nextTarget = event.relatedTarget as Node | null;
    if (nextTarget && event.currentTarget.contains(nextTarget)) return;
    if (dropTargetPath === ROOT_DROP_PATH) setDropTargetPath(null);
  };

  const handleRootDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    if (readOnly) return;
    const files = Array.from(event.dataTransfer.files ?? []);
    setDropTargetPath(null);
    if (files.length === 0) return;
    void handleDropUpload(ROOT_DROP_PATH, files);
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

  if (fileTree.length === 0) {
    return (
      <div
        data-testid="file-tree-root-dropzone"
        onDragOver={handleRootDragOver}
        onDragLeave={handleRootDragLeave}
        onDrop={handleRootDrop}
        className={`flex flex-col items-center justify-center gap-2 py-8 px-4 text-center transition-colors ${
          isRootDropTarget ? 'bg-primary/10 ring-1 ring-primary/30' : ''
        }`}
      >
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
      <div
        data-testid="file-tree-root-dropzone"
        onDragOver={handleRootDragOver}
        onDragLeave={handleRootDragLeave}
        onDrop={handleRootDrop}
        className={`py-1 transition-colors ${isRootDropTarget ? 'bg-primary/10 ring-1 ring-primary/30' : ''}`}
      >
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
          <FileTreeNode
            key={entry.path}
            entry={entry}
            depth={0}
            onCreate={openCreateDialog}
            onUpload={openUploadDialog}
            onDropUpload={handleDropUpload}
            dropTargetPath={dropTargetPath}
            onDropTargetChange={setDropTargetPath}
            onRename={openRenameDialog}
            onDelete={openDeleteDialog}
            readOnly={readOnly}
          />
        ))}
      </div>
      <FileTreeActionDialog
        dialogState={dialogState}
        inputValue={inputValue}
        dialogError={dialogError}
        isSubmitting={isSubmitting}
        isRtl={isRtl}
        onInputChange={setInputValue}
        onClose={closeDialog}
        onSubmit={() => void submitDialogAction()}
      />
    </>
  );
}
