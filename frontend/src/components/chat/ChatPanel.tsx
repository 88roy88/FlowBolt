import { useEffect, useRef, useMemo } from 'react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import type { AIModel } from '../../types';

function ModelSelector() {
  const { models, selectedModel, setSelectedModel, loadModels } = useChatStore();

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const grouped = useMemo(() => {
    const groups: Record<string, AIModel[]> = {};
    for (const model of models) {
      if (!groups[model.provider]) groups[model.provider] = [];
      groups[model.provider].push(model);
    }
    return groups;
  }, [models]);

  if (models.length === 0) return null;

  return (
    <select
      value={selectedModel ?? ''}
      onChange={(e) => setSelectedModel(e.target.value)}
      style={{
        background: 'var(--bg)',
        color: 'var(--text)',
        border: '1px solid var(--border)',
        borderRadius: '4px',
        padding: '3px 6px',
        fontSize: '12px',
        cursor: 'pointer',
        outline: 'none',
        maxWidth: '180px',
      }}
    >
      {Object.entries(grouped).map(([provider, providerModels]) => (
        <optgroup key={provider} label={provider}>
          {providerModels.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}

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
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span>Chat</span>
        <ModelSelector />
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
