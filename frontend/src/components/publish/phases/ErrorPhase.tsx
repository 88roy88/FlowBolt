import { useTranslation } from 'react-i18next';
import { AlertCircle } from 'lucide-react';
import { DialogTitle } from '../../ui/dialog';
import { BTN_SECONDARY } from '../styles';

interface ErrorPhaseProps {
  errorMessage: string;
  onClose: () => void;
}

export function ErrorPhase({ errorMessage, onClose }: ErrorPhaseProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full flex items-center justify-center bg-destructive/10 shrink-0">
          <AlertCircle className="w-5 h-5 text-destructive" />
        </div>
        <div>
          <DialogTitle className="text-lg font-semibold tracking-tight">
            {t('publish.publishFailed')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">{errorMessage}</p>
        </div>
      </div>
      <div className="w-full flex gap-3 pt-4">
        <button onClick={onClose} className={`flex-1 ${BTN_SECONDARY}`}>
          {t('common.close')}
        </button>
      </div>
    </div>
  );
}
