import { useTranslation } from 'react-i18next';
import { CheckCircle2, XCircle } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

export function DesignCompleteCard({ architecture, ux }: { architecture: boolean; ux: boolean }) {
  const { t } = useTranslation();
  return (
    <CardWrapper>
      <div className="text-xs text-muted-foreground mb-1.5">{t('chat.design.designComplete')}</div>
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-1.5">
          {architecture ? <CheckCircle2 size={13} className="text-success" /> : <XCircle size={13} className="text-destructive" />}
          <span>{t('chat.design.architecture')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          {ux ? <CheckCircle2 size={13} className="text-success" /> : <XCircle size={13} className="text-destructive" />}
          <span>{t('chat.design.uiux')}</span>
        </div>
      </div>
    </CardWrapper>
  );
}
