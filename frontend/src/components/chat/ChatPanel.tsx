import { useEffect, useRef } from 'react';
import { useChatStore } from '../../stores/chat';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import { WorkPlanView } from './WorkPlanView';
import { TaskProgress } from './TaskProgress';
import { PhaseIndicator } from './PhaseIndicator';
import { DesignProgress } from './DesignProgress';
import { FixProgressCard } from './cards/FixProgressCard';
import { FollowUpProgress } from './cards/FollowUpProgress';

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
  const showTypingDots = isStreaming && !currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress && !showPhaseIndicator;

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 flex flex-col gap-4 scroll-smooth">
        {messages.map((msg) => (
          <ChatMessage key={msg.id} message={msg} />
        ))}

        {showPhaseIndicator && <PhaseIndicator phase={agentPhase} />}
        {showDesignProgress && <DesignProgress designProgress={designProgress} />}
        {showOverview && <WorkPlanView overview={planOverview} />}
        {showTaskProgress && <TaskProgress tasks={executionTasks} />}
        {showFixProgress && <FixProgressCard steps={fixSteps} content={currentAssistantMessage} isLive />}
        {showFollowUpProgress && (
          <FollowUpProgress
            steps={followUpSteps}
            answer={currentAssistantMessage || undefined}
            filesChanged={actions.filter((a) => a.type === 'file' && a.path).map((a) => a.path!)}
            diffs={followUpDiffs.length > 0 ? followUpDiffs : undefined}
            isLive
          />
        )}

        {/* Typing indicator */}
        {showTypingDots && (
          <div className="flex justify-start animate-message-in">
            <div className="flex items-center gap-1.5 px-4 py-3 bg-assistant-bubble rounded-xl border border-border">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}

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
        <div className="flex items-center justify-between px-4 py-2 bg-danger-bg border-t border-destructive text-destructive text-[13px] shrink-0">
          <span>{error}</span>
          <button onClick={clearError} className="text-destructive px-1.5 py-0.5 text-xs">
            Dismiss
          </button>
        </div>
      )}

      <PromptInput />
    </div>
  );
}
