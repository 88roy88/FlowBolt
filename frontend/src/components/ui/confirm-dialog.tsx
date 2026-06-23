import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from './button';
import { Dialog, DialogContent, DialogClose, DialogTitle } from './dialog';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => void;
  confirmClassName?: string;
  confirmIcon?: ReactNode;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  body,
  confirmLabel,
  onConfirm,
  confirmClassName,
  confirmIcon,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogClose onClose={() => onOpenChange(false)} />
        <DialogTitle>{title}</DialogTitle>
        <p className="text-sm text-muted-foreground mt-2 mb-4">{body}</p>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="default" size="sm" className={confirmClassName} onClick={onConfirm}>
            {confirmIcon}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
