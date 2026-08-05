import { useTranslation } from 'react-i18next';
import { Check, Sparkles } from 'lucide-react';
import type { InterviewQuestion, InterviewAnswer } from '../../../types';
import { CardWrapper } from './CardWrapper';

interface InterviewAnsweredCardProps {
  questions: InterviewQuestion[];
  answers: InterviewAnswer[];
}

export function InterviewAnsweredCard({ questions, answers }: InterviewAnsweredCardProps) {
  const { t } = useTranslation();
  const answered = answers.filter((a) => a.values.length > 0);

  if (answered.length === 0) {
    return (
      <CardWrapper className="p-3.5">
        <p className="text-[13px] text-muted-foreground">{t('chat.interview.skip')}</p>
      </CardWrapper>
    );
  }

  const byId = new Map(questions.map((q) => [q.id, q]));

  return (
    <CardWrapper className="p-3.5">
      <div className="flex items-center gap-1.5 mb-2">
        <Sparkles size={12} className="text-primary shrink-0" />
        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{t('chat.interview.title')}</p>
      </div>
      <div className="flex flex-col gap-2">
        {answered.map((a) => (
          <div key={a.question_id} className="p-2.5 bg-background rounded-lg text-[13px]">
            <div dir="auto" className="font-semibold mb-1">{byId.get(a.question_id)?.question ?? a.question_id}</div>
            <div dir="auto" className="flex items-center gap-1.5 text-primary text-xs">
              <Check size={12} className="shrink-0" />
              <span dir="auto">{a.values.join(', ')}</span>
            </div>
          </div>
        ))}
      </div>
    </CardWrapper>
  );
}
