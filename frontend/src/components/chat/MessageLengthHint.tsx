import { useTranslation } from 'react-i18next';

/** Show the counter once the text reaches this share of the limit. */
const SHOW_AT = 0.9;

export function MessageLengthHint({ length, max }: { length: number; max: number | null }) {
  const { t } = useTranslation();
  if (max === null || length < max * SHOW_AT) return null;
  const over = length > max;
  return (
    <div
      data-testid="message-length-hint"
      className={`text-xs px-1.5 ${over ? 'text-destructive' : 'text-muted-foreground'}`}
    >
      {over
        ? t('chat.messageTooLong', { length: length.toLocaleString(), max: max.toLocaleString() })
        : `${length.toLocaleString()} / ${max.toLocaleString()}`}
    </div>
  );
}
