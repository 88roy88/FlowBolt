import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogTitle, DialogClose } from './dialog';
import { Copy, ExternalLink, Check, AlertCircle } from 'lucide-react';

interface PublishModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  url?: string;
  errorMessage?: string;
}

export function PublishModal({ open, onOpenChange, url, errorMessage }: PublishModalProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (!url) return;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isError = !!errorMessage;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md p-6 border-border/60 bg-surface/95 backdrop-blur-xl">
        <DialogClose onClose={() => onOpenChange(false)} />
        <div className="flex flex-col items-center justify-center text-center space-y-4">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center mb-2 ${isError ? 'bg-destructive/10' : 'bg-primary/10'}`}>
            {isError ? (
              <AlertCircle className="w-6 h-6 text-destructive" />
            ) : (
              <Check className="w-6 h-6 text-primary" />
            )}
          </div>
          
          <DialogTitle className="text-xl font-medium tracking-tight">
            {isError ? t('publish.publishFailed') : t('publish.successfullyPublished')}
          </DialogTitle>

          <p className="text-sm text-muted-foreground/80 pb-2">
            {isError
              ? errorMessage
              : t('publish.projectIsLive')}
          </p>
          
          {!isError && url && (
            <div className="flex items-center w-full gap-2 p-1.5 bg-muted/40 rounded-lg border border-border/50">
              <div className="flex-1 truncate px-3 py-1.5 text-sm font-mono text-muted-foreground bg-transparent outline-none">
                {url}
              </div>
              <button
                onClick={handleCopy}
                className="p-2 h-full rounded-md hover:bg-muted/80 text-foreground transition-colors group"
                title={t('publish.copyLink')}
              >
                {copied ? <Check size={16} className="text-primary" /> : <Copy size={16} className="group-hover:text-primary transition-colors" />}
              </button>
            </div>
          )}
          
          <div className="w-full flex gap-3 pt-4">
            <button
              onClick={() => onOpenChange(false)}
              className="flex-1 px-4 py-2.5 rounded-lg border border-border hover:bg-muted/50 transition-colors text-sm font-medium"
            >
              {t('common.close')}
            </button>
            {!isError && url && (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="flex-1 px-4 py-2.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground transition-colors text-sm font-medium flex justify-center items-center gap-2 shadow-sm"
                onClick={() => onOpenChange(false)}
              >
                <ExternalLink size={16} />
                {t('publish.openLive')}
              </a>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
