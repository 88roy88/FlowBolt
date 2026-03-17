import { useState, useRef, useCallback } from 'react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { Send } from 'lucide-react';

export function PromptInput() {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
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

  const disabled = isStreaming || !sessionId;

  return (
    <div
      style={{
        padding: 'var(--space-lg)',
        background: 'var(--surface)',
        boxShadow: 'var(--shadow-subtle-top)',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 'var(--space-md)',
          background: 'var(--surface-elevated)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-md) var(--space-lg)',
          boxShadow: 'var(--shadow-soft)',
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder={sessionId ? 'Describe what you want to build...' : 'Select a project first'}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            fontSize: 14,
            lineHeight: '1.5',
            maxHeight: '150px',
            opacity: disabled ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          style={{
            padding: 'var(--space-md) var(--space-lg)',
            borderRadius: 'var(--radius-lg)',
            background: value.trim() && !disabled ? 'var(--accent)' : 'transparent',
            color: value.trim() && !disabled ? '#fff' : 'var(--text-dim)',
            opacity: value.trim() && !disabled ? 1 : 0.5,
            flexShrink: 0,
          }}
          title="Send message"
        >
          <Send size={18} />
        </button>
      </div>
      {isStreaming && (
        <p style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: 'var(--space-sm)', textAlign: 'center' }}>
          AI is responding...
        </p>
      )}
    </div>
  );
}
