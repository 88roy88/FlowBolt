import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, type ButtonProps } from './button';
import { Dialog, DialogContent, DialogClose, DialogTitle } from './dialog';

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  confirmVariant?: ButtonProps['variant'];
  confirmIcon?: ReactNode;
  secondaryLabel?: string;
  secondaryVariant?: ButtonProps['variant'];
  onSecondary?: () => void;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  body,
  confirmLabel,
  onConfirm,
  confirmVariant = 'default',
  confirmIcon,
  secondaryLabel,
  secondaryVariant = 'outline',
  onSecondary,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogClose onClose={() => onOpenChange(false)} />
        <DialogTitle>{title}</DialogTitle>
        <div className="text-sm text-muted-foreground mt-2 mb-4">{body}</div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            {t('common.cancel')}
          </Button>
          {secondaryLabel && (
            <Button variant={secondaryVariant} size="sm" onClick={onSecondary}>
              {secondaryLabel}
            </Button>
          )}
          <Button variant={confirmVariant} size="sm" onClick={onConfirm}>
            {confirmIcon}
            {confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
