import { useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';

type Props = {
  initial: string;
  onSave: (content: string) => void;
  onCancel: () => void;
};

export function MessageEditor({ initial, onSave, onCancel }: Props) {
  const { t } = useTranslation();
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);
  const trimmed = value.trim();
  const canSave = !!trimmed && trimmed !== initial.trim();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 300) + 'px';
  }, [value]);

  useLayoutEffect(() => {
    const el = ref.current;
    el?.focus();
    el?.setSelectionRange(el.value.length, el.value.length);
  }, []);

  const save = () => {
    if (canSave) onSave(trimmed);
  };

  return (
    <div className="flex flex-col gap-2 w-full max-w-[85%]">
      <Textarea
        ref={ref}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            save();
          } else if (e.key === 'Escape') {
            onCancel();
          }
        }}
        className="resize-none bg-user-bubble border-primary/30 leading-relaxed"
      />
      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button size="sm" aria-disabled={!canSave} onClick={save}>
          {t('chat.rewind.send')}
        </Button>
      </div>
    </div>
  );
}
