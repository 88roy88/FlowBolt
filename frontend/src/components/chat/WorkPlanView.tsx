import { useState } from 'react';
import { Check, X, Pencil, Sparkles, ArrowRight } from 'lucide-react';
import type { PlanOverview } from '../../types';
import { useChatStore } from '../../stores/chat';

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
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '16px',
      maxWidth: '100%',
    }}>
      {/* Summary */}
      <p style={{
        fontSize: '14px',
        lineHeight: '1.6',
        marginBottom: '16px',
        color: 'var(--text)',
      }}>
        {overview.summary}
      </p>

      {/* Features */}
      {overview.features && overview.features.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px', color: 'var(--text-dim)' }}>
            What you'll get
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {overview.features.map((feature, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '8px',
                  padding: '8px 10px',
                  background: 'var(--bg)',
                  borderRadius: '8px',
                  fontSize: '13px',
                }}
              >
                <Sparkles size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <span style={{ fontWeight: 500 }}>{feature.title}</span>
                  <span style={{ color: 'var(--text-dim)' }}> — {feature.description}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Decisions */}
      {overview.decisions && overview.decisions.length > 0 && (
        <div style={{ marginBottom: '16px' }}>
          <h4 style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px', color: 'var(--text-dim)' }}>
            Key decisions
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {overview.decisions.map((decision) => (
              <div
                key={decision.id}
                style={{
                  padding: '10px 12px',
                  background: 'var(--bg)',
                  borderRadius: '8px',
                  fontSize: '13px',
                }}
              >
                <div style={{ fontWeight: 500, marginBottom: '4px' }}>
                  {decision.title}
                </div>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  color: 'var(--accent)',
                  fontSize: '12px',
                  marginBottom: '4px',
                }}>
                  <ArrowRight size={12} />
                  {decision.chosen}
                </div>
                {decision.alternatives && decision.alternatives.length > 0 && (
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
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
        <div style={{ marginBottom: '12px' }}>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What would you like to change? e.g. 'Use a dark theme instead' or 'I prefer local storage over a database'"
            autoFocus
            style={{
              width: '100%',
              minHeight: '60px',
              padding: '8px 10px',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              fontSize: '13px',
              resize: 'vertical',
              color: 'var(--text)',
            }}
          />
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '8px' }}>
        <button
          onClick={() => respondToPlan('accept')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            background: 'var(--success)',
            color: 'var(--text-on-accent)',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <Check size={14} />
          Looks good, build it
        </button>
        <button
          onClick={handleModify}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            background: 'var(--warning)',
            color: 'var(--text-on-accent)',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <Pencil size={14} />
          {modifyMode ? 'Send feedback' : 'Change something'}
        </button>
        <button
          onClick={() => respondToPlan('reject')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            padding: '6px 14px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            background: 'transparent',
            color: 'var(--text-dim)',
            border: '1px solid var(--border)',
            cursor: 'pointer',
          }}
        >
          <X size={14} />
          Start over
        </button>
      </div>
    </div>
  );
}
