import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Sparkles, Pencil, ChevronLeft, ChevronRight } from 'lucide-react';
import type { InterviewQuestion, InterviewAnswer } from '../../types';
import { useChatStore } from '../../stores/chat';
import { Button } from '../ui/button';
import { CardWrapper } from './cards/CardWrapper';

interface InterviewCardProps {
  questions: InterviewQuestion[];
}

function OptionIndicator({ multiSelect, active }: { multiSelect: boolean; active: boolean }) {
  if (multiSelect) {
    return (
      <span className={`h-3.5 w-3.5 rounded border shrink-0 flex items-center justify-center ${active ? 'bg-primary border-primary' : 'border-border'}`}>
        {active && <Check size={10} className="text-primary-foreground" />}
      </span>
    );
  }
  return (
    <span className={`h-3.5 w-3.5 rounded-full border shrink-0 flex items-center justify-center ${active ? 'border-primary' : 'border-border'}`}>
      {active && <span className="h-1.5 w-1.5 rounded-full bg-primary" />}
    </span>
  );
}

export function InterviewCard({ questions }: InterviewCardProps) {
  const { t } = useTranslation();
  const respondToInterview = useChatStore((s) => s.respondToInterview);
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [otherText, setOtherText] = useState<Record<string, string>>({});
  const [otherFocusedId, setOtherFocusedId] = useState('');

  const q = questions[step];
  const isLast = step === questions.length - 1;
  const cur = selected[q.id] ?? [];
  const otherActive = !!(otherText[q.id] ?? '').trim() || otherFocusedId === q.id;

  const focusOther = () => {
    setOtherFocusedId(q.id);
    if (!q.multi_select) {
      setSelected((prev) => ({ ...prev, [q.id]: [] }));
    }
  };

  const toggle = (label: string) => {
    setSelected((prev) => {
      const prevValues = prev[q.id] ?? [];
      if (q.multi_select) {
        const next = prevValues.includes(label) ? prevValues.filter((l) => l !== label) : [...prevValues, label];
        return { ...prev, [q.id]: next };
      }
      return { ...prev, [q.id]: prevValues.includes(label) ? [] : [label] };
    });
    if (!q.multi_select) {
      setOtherText((prev) => ({ ...prev, [q.id]: '' }));
    }
  };

  const submit = () => {
    const answers: InterviewAnswer[] = questions.map((question) => {
      const values = [...(selected[question.id] ?? [])];
      const extra = (otherText[question.id] ?? '').trim();
      if (extra) values.push(extra);
      return { question_id: question.id, values };
    });
    respondToInterview('submit', answers);
  };

  const advance = () => (isLast ? submit() : setStep((s) => s + 1));

  return (
    <CardWrapper accent="primary">
      <div className="flex items-center gap-1.5 mb-2">
        <Sparkles size={12} className="text-primary shrink-0" />
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{t('chat.interview.title')}</p>
        {questions.length > 1 && (
          <span className="ms-auto text-[11px] tabular-nums text-muted-foreground">{step + 1}/{questions.length}</span>
        )}
      </div>

      {questions.length > 1 && (
        <div
          className="h-1 w-full rounded-full bg-muted overflow-hidden mb-3"
          aria-label={t('chat.interview.progress', { current: step + 1, total: questions.length })}
        >
          <div className="h-full bg-primary transition-[width] duration-300" style={{ width: `${((step + 1) / questions.length) * 100}%` }} />
        </div>
      )}

      <div key={step} className="animate-message-in">
        {q.header && (
          <p dir="auto" className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground mb-1">{q.header}</p>
        )}
        <div dir="auto" className="text-[15px] font-semibold leading-snug mb-2">{q.question}</div>
        {q.multi_select && (
          <p className="text-[11px] text-muted-foreground mb-2">{t('chat.interview.selectHint')}</p>
        )}
        <div className="flex flex-col gap-1">
          {q.options.map((opt) => {
            const active = cur.includes(opt.label);
            return (
              <button
                key={opt.label}
                type="button"
                onClick={() => toggle(opt.label)}
                aria-pressed={active}
                className={`w-full flex items-start gap-2 px-2.5 py-1.5 text-start rounded-lg border text-[13px] transition-colors ${
                  active ? 'border-primary bg-accent-bg-strong' : 'border-border hover:bg-muted/50'
                }`}
              >
                <OptionIndicator multiSelect={q.multi_select} active={active} />
                <span dir="auto" className="min-w-0">
                  <span className={active ? 'font-medium' : ''}>{opt.label}</span>
                  {opt.description && <span className="block text-[11px] text-muted-foreground leading-snug">{opt.description}</span>}
                </span>
              </button>
            );
          })}

          <label
            className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border cursor-text transition-colors ${
              otherActive ? 'border-primary bg-accent-bg-strong' : 'border-border hover:bg-muted/50'
            }`}
          >
            <OptionIndicator multiSelect={q.multi_select} active={otherActive} />
            <Pencil size={11} className="text-muted-foreground shrink-0" />
            <input
              dir="auto"
              value={otherText[q.id] ?? ''}
              onFocus={focusOther}
              onBlur={() => setOtherFocusedId('')}
              onChange={(e) => setOtherText((prev) => ({ ...prev, [q.id]: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key !== 'Enter') return;
                e.preventDefault();
                advance();
              }}
              placeholder={t('chat.interview.other')}
              aria-label={t('chat.interview.other')}
              className="flex-1 min-w-0 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground"
            />
          </label>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-border">
        {step > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setStep((s) => s - 1)} className="text-muted-foreground">
            <ChevronLeft size={13} className="rtl:rotate-180" />
            {t('chat.interview.back')}
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={() => respondToInterview('skip')} className="ms-auto text-muted-foreground">
          {t('chat.interview.skipAll')}
        </Button>
        {isLast ? (
          <Button variant="success" size="sm" onClick={submit}>
            <Check size={13} />
            {t('chat.interview.submit')}
          </Button>
        ) : (
          <Button variant="success" size="sm" onClick={() => setStep((s) => s + 1)}>
            {t('chat.interview.next')}
            <ChevronRight size={13} className="rtl:rotate-180" />
          </Button>
        )}
      </div>
    </CardWrapper>
  );
}
