import { useState, useRef, useCallback } from 'react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { ArrowUp, Loader2, Database, X } from 'lucide-react';
import { CaseSelector } from './CaseSelector';

export function PromptInput() {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [showCaseSelector, setShowCaseSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const selectedCases = useChatStore((s) => s.selectedCases);
  const removeCase = useChatStore((s) => s.removeCase);
  const sessionId = useSessionStore((s) => s.sessionId);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || !sessionId) return;
    sendMessage(trimmed);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isBusy = isStreaming || (agentPhase !== 'idle' && agentPhase !== 'awaiting_approval' && agentPhase !== 'complete');
  const disabled = isBusy || !sessionId;
  const canSend = !!value.trim() && !disabled;

  const placeholder = !sessionId
    ? 'Select a project first'
    : agentPhase === 'awaiting_approval'
      ? 'Review the plan above, then accept, modify, or reject'
      : isBusy
        ? 'AI is working...'
        : 'Describe what you want to build...';

  const busyLabel =
    agentPhase === 'classifying' ? 'Analyzing' :
    agentPhase === 'fetching_cases' ? 'Fetching case data' :
    agentPhase === 'designing' ? 'Designing' :
    agentPhase === 'planning' ? 'Planning' :
    agentPhase === 'executing' ? 'Building' :
    'Thinking';

  return (
    <div style={{
      padding: '10px 14px',
      borderTop: '1px solid var(--border)',
      background: 'var(--surface)',
      flexShrink: 0,
    }}>
      {/* Case selector - shown when toggled */}
      {!isBusy && sessionId && showCaseSelector && (
        <div style={{ marginBottom: '10px', position: 'relative' }}>
          <CaseSelector isOpen={showCaseSelector} />
        </div>
      )}
      {/* Selected case badges (always visible when cases are selected) */}
      {!showCaseSelector && selectedCases.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          marginBottom: '8px',
        }}>
          {selectedCases.map((c) => (
            <div
              key={c.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
                border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)',
                borderRadius: '6px',
                fontSize: '12px',
              }}
            >
              <span style={{ fontWeight: 500 }}>{c.name}</span>
              <button
                onClick={() => removeCase(c.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '16px',
                  height: '16px',
                  borderRadius: '3px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-dim)',
                  padding: 0,
                }}
                title="Remove case"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      {isBusy && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
          fontSize: '12px',
          color: 'var(--accent)',
          marginBottom: '8px',
        }}>
          <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
          <span>{busyLabel}...</span>
        </div>
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          background: 'var(--bg)',
          border: `1px solid ${focused && !disabled ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: '12px',
          padding: '4px 4px 4px 14px',
          transition: 'border-color 0.15s, box-shadow 0.15s',
          boxShadow: focused && !disabled
            ? '0 0 0 2px color-mix(in srgb, var(--accent) 12%, transparent)'
            : 'var(--shadow-sm)',
        }}
      >
        {/* Case selector toggle icon */}
        {!isBusy && sessionId && (
          <button
            onClick={() => setShowCaseSelector((v) => !v)}
            style={{
              position: 'relative',
              width: '32px',
              height: '32px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: '8px',
              background: showCaseSelector
                ? 'color-mix(in srgb, var(--accent) 15%, transparent)'
                : 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: selectedCases.length > 0 ? 'var(--accent)' : 'var(--text-dim)',
              flexShrink: 0,
              transition: 'background 0.15s, color 0.15s',
            }}
            title={showCaseSelector ? 'Hide case selector' : 'Attach cases'}
          >
            <Database size={16} />
            {selectedCases.length > 0 && (
              <span style={{
                position: 'absolute',
                top: '2px',
                right: '2px',
                width: '14px',
                height: '14px',
                borderRadius: '7px',
                background: 'var(--accent)',
                color: 'var(--text-on-accent)',
                fontSize: '9px',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                lineHeight: 1,
              }}>
                {selectedCases.length}
              </span>
            )}
          </button>
        )}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            fontSize: '14px',
            lineHeight: '1.5',
            maxHeight: '200px',
            padding: '6px 0',
            opacity: disabled ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={!canSend}
          style={{
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: canSend ? 'var(--accent)' : 'var(--border)',
            color: canSend ? 'var(--text-on-accent)' : 'var(--text-dim)',
            opacity: canSend ? 1 : 0.4,
            flexShrink: 0,
            transition: 'background 0.15s, opacity 0.15s',
            cursor: canSend ? 'pointer' : 'default',
          }}
          title="Send message"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  );
}
