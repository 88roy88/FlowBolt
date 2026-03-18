import { useEffect, useRef, useMemo, useState } from 'react';
import { Loader2, CheckCircle2, Search, Wrench, Save, TestTube, RefreshCw, XCircle } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage, FollowUpProgress } from './ChatMessage';
import { PromptInput } from './PromptInput';
import { ChevronDown, Check } from 'lucide-react';
import { ThemeToggle } from '../layout/ThemeToggle';
import { WorkPlanView } from './WorkPlanView';
import { TaskProgress } from './TaskProgress';
import type { AIModel, AgentPhase, FixStep } from '../../types';

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
          gap: '6px',
          padding: '4px 10px',
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
                  padding: '6px 10px',
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
                      padding: '6px 10px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
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

const PHASE_LABELS: Record<AgentPhase, string> = {
  idle: '',
  classifying: 'Analyzing your request...',
  designing: 'Designing the application...',
  planning: 'Building work plan...',
  awaiting_approval: 'Review the plan below',
  executing: 'Building...',
  fixing: 'Fixing error...',
  exploring: 'Exploring codebase...',
  complete: 'Done!',
};

function getStepIcon(step: FixStep['step']) {
  switch (step) {
    case 'discover':
      return Search;
    case 'generate':
      return Wrench;
    case 'write':
      return Save;
    case 'validate':
      return TestTube;
    case 'retry':
      return RefreshCw;
  }
}

function FixProgressLive({ steps, content }: { steps: FixStep[]; content?: string }) {
  const completed = steps.filter((s) => s.status === 'completed').length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const total = steps.length;
  const hasRunning = steps.some((s) => s.status === 'running');

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '14px 16px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '12px',
        fontSize: '13px',
        fontWeight: 500,
        color: failed > 0 ? 'var(--danger)' : hasRunning ? 'var(--accent)' : 'var(--success)',
      }}>
        {hasRunning ? (
          <>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            Fixing error...
          </>
        ) : failed > 0 ? (
          <>
            <XCircle size={14} />
            Error fix completed with issues
          </>
        ) : (
          <>
            <CheckCircle2 size={14} />
            Error fixed successfully!
          </>
        )}
      </div>

      {/* Explanation text */}
      {content && (
        <div style={{
          marginBottom: '12px',
          padding: '10px',
          background: 'var(--bg)',
          borderRadius: '6px',
          fontSize: '12px',
          lineHeight: '1.6',
          color: 'var(--text)',
        }}>
          {content}
        </div>
      )}

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {steps.map((step) => {
          const StepIcon = getStepIcon(step.step);
          return (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 8px',
                borderRadius: '6px',
                background: step.status === 'running' ? 'rgba(137, 180, 250, 0.08)' : 'transparent',
                fontSize: '13px',
                transition: 'background 0.2s',
              }}
            >
              {step.status === 'running' ? (
                <Loader2 size={14} style={{ color: 'var(--accent)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
              ) : step.status === 'completed' ? (
                <StepIcon size={14} style={{ color: 'var(--success)', flexShrink: 0 }} />
              ) : (
                <XCircle size={14} style={{ color: 'var(--danger)', flexShrink: 0 }} />
              )}
              <span style={{ color: step.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>
                {step.message}
              </span>
            </div>
          );
        })}
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
    agentPhase, planOverview, executionTasks, designProgress, fixSteps, followUpSteps, followUpDiffs,
  } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentAssistantMessage, agentPhase, executionTasks, fixSteps, followUpSteps]);

  const showDesignProgress = agentPhase === 'designing';
  const showOverview = agentPhase === 'awaiting_approval' && planOverview;
  const showTaskProgress = (agentPhase === 'executing' || agentPhase === 'complete') && executionTasks.length > 0;
  const showFixProgress = fixSteps.length > 0 && isStreaming;
  const showFollowUpProgress = followUpSteps.length > 0 && isStreaming;
  const showStreamingMessage = isStreaming && currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress;
  const showPhaseIndicator = agentPhase === 'classifying' || agentPhase === 'planning' || (agentPhase === 'exploring' && followUpSteps.length === 0);

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
          padding: '10px 16px',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface)',
          fontSize: '13px',
          fontWeight: 600,
          flexShrink: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 8,
        }}
      >
        <span>Chat</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ThemeToggle />
          <ModelSelector />
        </div>
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

        {/* Fix progress */}
        {showFixProgress && <FixProgressLive steps={fixSteps} content={currentAssistantMessage} />}

        {/* Follow-up exploration progress */}
        {showFollowUpProgress && (
          <FollowUpProgress
            steps={followUpSteps}
            answer={currentAssistantMessage || undefined}
            filesChanged={actions.filter((a) => a.type === 'file' && a.path).map((a) => a.path!)}
            diffs={followUpDiffs.length > 0 ? followUpDiffs : undefined}
            isLive
          />
        )}

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
