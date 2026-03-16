import { useState, useRef, useCallback } from 'react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { Send } from 'lucide-react';

export function PromptInput() {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const sessionId = useSessionStore((s) => s.sessionId);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 150) + 'px';
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

  const placeholder = !sessionId
    ? 'Select a project first'
    : agentPhase === 'awaiting_approval'
      ? 'Review the plan above, then accept, modify, or reject'
      : isBusy
        ? 'AI is working...'
        : 'Describe what you want to build...';

  return (
    <div style={{
      padding: '12px 16px',
      borderTop: '1px solid var(--border)',
      background: 'var(--surface)',
      flexShrink: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '8px',
        background: 'var(--bg)',
        border: '1px solid var(--border)',
        borderRadius: '10px',
        padding: '8px 12px',
      }}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            fontSize: '14px',
            lineHeight: '1.5',
            maxHeight: '150px',
            opacity: disabled ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          style={{
            padding: '6px',
            borderRadius: '6px',
            color: value.trim() && !disabled ? 'var(--accent)' : 'var(--text-dim)',
            opacity: value.trim() && !disabled ? 1 : 0.4,
            flexShrink: 0,
          }}
          title="Send message"
        >
          <Send size={18} />
        </button>
      </div>
      {isBusy && (
        <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '6px', textAlign: 'center' }}>
          {agentPhase === 'classifying' ? 'Analyzing...' :
           agentPhase === 'designing' ? 'Designing...' :
           agentPhase === 'planning' ? 'Planning...' :
           agentPhase === 'executing' ? 'Building...' :
           'AI is responding...'}
        </p>
      )}
    </div>
  );
}
