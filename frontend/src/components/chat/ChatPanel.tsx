import { useEffect, useRef } from 'react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';

export function ChatPanel() {
  const { messages, isStreaming, currentAssistantMessage, actions } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentAssistantMessage]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        fontSize: '13px',
        fontWeight: 600,
        flexShrink: 0,
      }}>
        Chat
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {/* Streaming message */}
        {isStreaming && (
          <ChatMessage
            message={{
              id: '__streaming__',
              role: 'assistant',
              content: currentAssistantMessage,
              actions: actions.length > 0 ? actions : undefined,
              timestamp: Date.now(),
            }}
            isStreaming
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <PromptInput />
    </div>
  );
}
