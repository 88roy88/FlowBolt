import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, Sparkles } from 'lucide-react';

function Row({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-0.5 px-0.5 min-h-5" aria-live="polite" data-testid="enhance-row">
      {children}
    </div>
  );
}

export function EnhanceRow({
  isEnhancing,
  canUndo,
  onEnhance,
  onUndo,
}: {
  isEnhancing: boolean;
  canUndo: boolean;
  onEnhance: () => void;
  onUndo: () => void;
}) {
  const { t } = useTranslation();

  if (isEnhancing) {
    return (
      <Row>
        <span className="inline-flex items-center gap-1.5 h-5 px-1 text-[11.5px] text-muted-foreground opacity-80 cursor-default">
          <Loader2 size={12} className="animate-spin" />
          {t('chat.enhance.enhancing')}
        </span>
      </Row>
    );
  }

  if (canUndo) {
    return (
      <Row>
        <span className="inline-flex items-center gap-1.5 h-5 px-1 text-[11.5px] text-muted-foreground cursor-default select-none">
          <Sparkles size={12} />
          {t('chat.enhance.enhanced')}
        </span>
        <button
          type="button"
          onClick={onUndo}
          title={t('chat.enhance.undoTitle')}
          className="h-5 px-2 rounded-full text-[11.5px] text-primary hover:bg-muted/50 hover:underline"
        >
          {t('chat.enhance.undo')}
        </button>
      </Row>
    );
  }

  return (
    <Row>
      <button
        type="button"
        onClick={onEnhance}
        title={t('chat.enhance.actionTitle')}
        data-testid="enhance-button"
        className="inline-flex items-center gap-1.5 h-5 px-2 rounded-full text-[11.5px] text-muted-foreground hover:bg-muted/50 hover:text-foreground transition-colors"
      >
        <Sparkles size={12} />
        {t('chat.enhance.action')}
      </button>
    </Row>
  );
}
