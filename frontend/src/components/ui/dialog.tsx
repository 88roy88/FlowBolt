import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

function Dialog({ open, onOpenChange, children }: DialogProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center bg-overlay"
      onClick={() => onOpenChange(false)}
    >
      {children}
    </div>
  );
}

const DialogContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'relative max-h-[80vh] max-w-[500px] overflow-auto rounded-xl border border-border bg-card p-5',
        className,
      )}
      onClick={(e) => e.stopPropagation()}
      {...props}
    >
      {children}
    </div>
  ),
);
DialogContent.displayName = 'DialogContent';

function DialogClose({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  return (
    <button
      onClick={onClose}
      className="absolute top-3 end-3 rounded p-1 text-muted-foreground hover:text-foreground"
      title={t('common.close')}
    >
      <X size={18} />
    </button>
  );
}

function DialogTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('pe-6 text-lg font-semibold', className)} {...props} />;
}

export { Dialog, DialogContent, DialogClose, DialogTitle };
