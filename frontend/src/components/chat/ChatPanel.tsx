import { useEffect, useRef, useMemo, useState } from 'react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import type { AIModel } from '../../types';
import { ChevronDown, Check } from 'lucide-react';
import { ThemeToggle } from '../layout/ThemeToggle';

function ModelSelector() {
  const { models, selectedModel, setSelectedModel, loadModels } = useChatStore();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

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

  const current = models.find((m) => m.id === selectedModel) ?? models[0];

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-sm)',
          padding: 'var(--space-sm) var(--space-md)',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: '999px',
          color: 'var(--text)',
          fontSize: '12px',
          cursor: 'pointer',
          maxWidth: '260px',
        }}
        title={current?.id ?? 'Loading models…'}
      >
        <span style={{ fontWeight: 500, color: 'var(--text-dim)' }}>Model</span>
        <span
          style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            textAlign: 'left',
          }}
        >
          {current?.name ?? current?.id ?? 'Loading models…'}
        </span>
        <ChevronDown size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '110%',
            right: 0,
            marginTop: '4px',
            minWidth: '260px',
            maxHeight: '320px',
            overflow: 'auto',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.35)',
            zIndex: 40,
          }}
        >
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div
                style={{
                  padding: 'var(--space-sm) var(--space-md)',
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-dim)',
                  borderBottom: '1px solid rgba(255,255,255,0.03)',
                  background: 'rgba(0,0,0,0.25)',
                }}
              >
                {provider}
              </div>
              {providerModels.map((m) => {
                const isActive = (selectedModel ?? current.id) === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setSelectedModel(m.id);
                      setOpen(false);
                    }}
                    style={{
                      width: '100%',
                      padding: 'var(--space-md) var(--space-lg)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-md)',
                      background: isActive ? 'rgba(76, 167, 255, 0.15)' : 'transparent',
                      border: 'none',
                      borderBottom: '1px solid rgba(255,255,255,0.03)',
                      color: 'var(--text)',
                      fontSize: '12px',
                      textAlign: 'left',
                      cursor: 'pointer',
                    }}
                  >
                    <Check
                      size={14}
                      style={{
                        opacity: isActive ? 1 : 0,
                        color: 'var(--accent)',
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.name}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
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
      <div
        style={{
          padding: 'var(--space-lg) var(--space-lg)',
          background: 'var(--surface-elevated)',
          boxShadow: 'var(--shadow-subtle)',
          fontSize: '13px',
          fontWeight: 600,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 'var(--space-lg)',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-sm)',
          }}
        >
          <span>Chat</span>
          <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>
            Describe what you want to build
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <ThemeToggle />
          <ModelSelector />
        </div>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: 'var(--space-lg)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-lg)',
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
