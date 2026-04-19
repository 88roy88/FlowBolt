import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Copy, ExternalLink } from 'lucide-react';
import { DialogTitle } from '../../dialog';
import { BTN_PRIMARY, BTN_SECONDARY } from '../styles';

interface SuccessPhaseProps {
  resultUrl: string;
  onClose: () => void;
}

export function SuccessPhase({ resultUrl, onClose }: SuccessPhaseProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const displayUrl = `${window.location.origin}${resultUrl}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(displayUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full flex items-center justify-center bg-primary/10 shrink-0">
          <Check className="w-5 h-5 text-primary" />
        </div>
        <div>
          <DialogTitle className="text-lg font-semibold tracking-tight">
            {t('publish.successfullyPublished')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">{t('publish.projectIsLive')}</p>
        </div>
      </div>

      <div className="flex items-center w-full gap-2 p-1.5 bg-muted/40 rounded-lg border border-border/50">
        <div className="flex-1 truncate px-3 py-1.5 text-sm font-mono text-muted-foreground bg-transparent outline-none">
          {displayUrl}
        </div>
        <button
          onClick={handleCopy}
          className="p-2 h-full rounded-md hover:bg-muted/80 text-foreground transition-colors group"
          title={t('publish.copyLink')}
        >
          {copied
            ? <Check size={16} className="text-primary" />
            : <Copy size={16} className="group-hover:text-primary transition-colors" />}
        </button>
      </div>

      <div className="w-full flex gap-3 pt-4">
        <button onClick={onClose} className={`flex-1 ${BTN_SECONDARY}`}>
          {t('common.close')}
        </button>
        <a
          href={resultUrl}
          target="_blank"
          rel="noreferrer"
          className={BTN_PRIMARY}
          onClick={onClose}
        >
          <ExternalLink size={16} />
          {t('publish.openLive')}
        </a>
      </div>
    </div>
  );
}
