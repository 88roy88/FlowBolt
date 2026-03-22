import { useState } from 'react';
import { Check, X, Pencil, Sparkles, ArrowRight } from 'lucide-react';
import type { PlanOverview } from '../../types';
import { useChatStore } from '../../stores/chat';
import { Button } from '../ui/button';
import { Textarea } from '../ui/textarea';
import { CardWrapper } from './cards/CardWrapper';

interface WorkPlanViewProps {
  overview: PlanOverview;
}

export function WorkPlanView({ overview }: WorkPlanViewProps) {
  const [modifyMode, setModifyMode] = useState(false);
  const [feedback, setFeedback] = useState('');
  const respondToPlan = useChatStore((s) => s.respondToPlan);

  const handleModify = () => {
    if (modifyMode && feedback.trim()) {
      respondToPlan('modify', feedback.trim());
      setModifyMode(false);
      setFeedback('');
    } else {
      setModifyMode(true);
    }
  };

  return (
    <CardWrapper className="p-4">
      {/* Summary */}
      <p className="text-sm leading-relaxed mb-4">{overview.summary}</p>

      {/* Features */}
      {overview.features && overview.features.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[13px] font-semibold text-muted-foreground mb-2">What you'll get</h4>
          <div className="flex flex-col gap-1.5">
            {overview.features.map((feature, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-2 bg-background rounded-lg text-[13px]"
                style={{ animation: `staggerFadeIn 0.3s cubic-bezier(0.16,1,0.3,1) ${i * 60}ms both` }}
              >
                <Sparkles size={14} className="text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="font-medium">{feature.title}</span>
                  <span className="text-muted-foreground"> — {feature.description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Decisions */}
      {overview.decisions && overview.decisions.length > 0 && (
        <div className="mb-4">
          <h4 className="text-[13px] font-semibold text-muted-foreground mb-2">Key decisions</h4>
          <div className="flex flex-col gap-2">
            {overview.decisions.map((decision) => (
              <div key={decision.id} className="p-2.5 bg-background rounded-lg text-[13px]">
                <div className="font-medium mb-1">{decision.title}</div>
                <div className="flex items-center gap-1.5 text-primary text-xs mb-1">
                  <ArrowRight size={12} />
                  {decision.chosen}
                </div>
                {decision.alternatives && decision.alternatives.length > 0 && (
                  <div className="text-[11px] text-muted-foreground">
                    Other options: {decision.alternatives.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modify feedback input */}
      {modifyMode && (
        <div className="mb-3">
          <Textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What would you like to change? e.g. 'Use a dark theme instead' or 'I prefer local storage over a database'"
            autoFocus
            className="bg-background"
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button variant="success" onClick={() => respondToPlan('accept')} className="hover:-translate-y-0.5 transition-transform duration-150">
          <Check size={14} />
          Looks good, build it
        </Button>
        <Button variant="warning" onClick={handleModify} className="hover:-translate-y-0.5 transition-transform duration-150">
          <Pencil size={14} />
          {modifyMode ? 'Send feedback' : 'Change something'}
        </Button>
        <Button variant="outline" onClick={() => respondToPlan('reject')} className="hover:-translate-y-0.5 transition-transform duration-150">
          <X size={14} />
          Start over
        </Button>
      </div>
    </CardWrapper>
  );
}
