import { useTranslation } from 'react-i18next';
import type { FileEntry } from '../../types';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';

export type FileActionDialogState =
  | { mode: 'create'; basePath: string }
  | { mode: 'rename'; entry: FileEntry }
  | { mode: 'delete'; entry: FileEntry }
  | null;

interface FileTreeActionDialogProps {
  dialogState: FileActionDialogState;
  inputValue: string;
  dialogError: string | null;
  isSubmitting: boolean;
  isRtl: boolean;
  onInputChange: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}

export function FileTreeActionDialog({
  dialogState,
  inputValue,
  dialogError,
  isSubmitting,
  isRtl,
  onInputChange,
  onClose,
  onSubmit,
}: FileTreeActionDialogProps) {
  const { t } = useTranslation();
  const isDialogOpen = dialogState !== null;
  const isDeleteMode = dialogState?.mode === 'delete';
  const titleKey = { create: 'editor.createFile', rename: 'editor.renameFile', delete: 'editor.deleteFile' } as const;
  const dialogTitle = dialogState ? t(titleKey[dialogState.mode]) : '';
  const dialogDescription = dialogState?.mode === 'delete'
    ? t('editor.confirmDeleteFile', { name: dialogState.entry.name })
    : undefined;

  return (
    <Dialog open={isDialogOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent className="w-full max-w-[430px]">
        <DialogClose onClose={onClose} />
        <DialogTitle className={isRtl ? 'text-right' : undefined}>{dialogTitle}</DialogTitle>
        {dialogDescription ? (
          <p className={`mt-2 text-sm text-muted-foreground ${isRtl ? 'text-right' : ''}`}>{dialogDescription}</p>
        ) : (
          <div className="mt-3">
            <Input
              autoFocus
              value={inputValue}
              className={isRtl ? 'text-right placeholder:text-right' : undefined}
              placeholder={dialogState?.mode === 'create' ? t('editor.newFilePrompt') : t('editor.renamePrompt')}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onSubmit();
              }}
            />
          </div>
        )}
        {dialogError && (
          <p className={`mt-2 text-xs text-destructive ${isRtl ? 'text-right' : ''}`}>{dialogError}</p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            {t('common.cancel')}
          </Button>
          <Button
            variant={isDeleteMode ? 'destructive' : 'default'}
            onClick={onSubmit}
            disabled={isSubmitting}
          >
            {isDeleteMode ? t('common.delete') : dialogState?.mode === 'rename' ? t('common.save') : t('common.create')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
