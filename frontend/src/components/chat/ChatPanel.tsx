import { useEffect, useRef, useMemo } from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import { WorkPlanView } from './WorkPlanView';
import { TaskProgress } from './TaskProgress';
import type { AIModel, AgentPhase } from '../../types';

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
        maxWidth: '400px',
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

const PHASE_LABELS: Record<AgentPhase, string> = {
  idle: '',
  classifying: 'Analyzing your request...',
  designing: 'Designing the application...',
  planning: 'Building work plan...',
  awaiting_approval: 'Review the plan below',
  executing: 'Building...',
  complete: 'Done!',
};

function DesignProgress({ designProgress }: { designProgress: { architecture: string | null; ux: string | null } }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '14px 16px',
    }}>
      <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '10px' }}>
        Designing...
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          {designProgress.architecture ? (
            <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          ) : (
            <Loader2 size={14} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
          )}
          <span>Architecture</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
          {designProgress.ux ? (
            <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
          ) : (
            <Loader2 size={14} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />
          )}
          <span>UI/UX</span>
        </div>
      </div>
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function PhaseIndicator({ phase }: { phase: AgentPhase }) {
  const label = PHASE_LABELS[phase];
  if (!label) return null;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '8px 14px',
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      fontSize: '13px',
      color: 'var(--text-dim)',
    }}>
      {phase !== 'complete' && phase !== 'awaiting_approval' && (
        <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
      )}
      {phase === 'complete' && (
        <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />
      )}
      {label}
    </div>
  );
}

export function ChatPanel() {
  const {
    messages, isStreaming, currentAssistantMessage, actions, error, clearError,
    agentPhase, planOverview, executionTasks, designProgress,
  } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentAssistantMessage, agentPhase, executionTasks]);

  const showDesignProgress = agentPhase === 'designing';
  const showOverview = agentPhase === 'awaiting_approval' && planOverview;
  const showTaskProgress = (agentPhase === 'executing' || agentPhase === 'complete') && executionTasks.length > 0;
  const showStreamingMessage = isStreaming && currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress;
  const showPhaseIndicator = agentPhase === 'classifying' || agentPhase === 'planning';

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

        {/* Phase indicator for classifying/planning */}
        {showPhaseIndicator && <PhaseIndicator phase={agentPhase} />}

        {/* Design progress */}
        {showDesignProgress && <DesignProgress designProgress={designProgress} />}

        {/* Plan overview for approval */}
        {showOverview && <WorkPlanView overview={planOverview} />}

        {/* Task execution progress */}
        {showTaskProgress && <TaskProgress tasks={executionTasks} />}

        {/* Streaming message (follow-up flow) */}
        {showStreamingMessage && (
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

      {/* Error banner */}
      {error && (
        <div style={{
          padding: '8px 16px',
          background: 'rgba(243, 139, 168, 0.15)',
          borderTop: '1px solid var(--danger)',
          color: 'var(--danger)',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <span>{error}</span>
          <button
            onClick={clearError}
            style={{ color: 'var(--danger)', padding: '2px 6px', fontSize: '12px' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Input */}
      <PromptInput />
    </div>
  );
}
