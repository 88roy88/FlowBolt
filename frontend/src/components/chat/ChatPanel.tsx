import { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDown, Loader2 } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import { WorkPlanView } from './WorkPlanView';
import { TaskProgress } from './TaskProgress';
import { PhaseIndicator } from './PhaseIndicator';
import { DesignProgress } from './DesignProgress';
import { FixProgressCard } from './cards/FixProgressCard';
import { FollowUpProgress } from './cards/FollowUpProgress';

export function ChatPanel() {
  const { t } = useTranslation();
  const {
    messages, isStreaming, currentAssistantMessage, actions, error, clearError,
    agentPhase, planOverview, executionTasks, designProgress, fixSteps, followUpSteps, followUpDiffs, historyLoaded,
  } = useChatStore();
  const isCreating = useSessionStore((s) => s.isCreating);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Auto-scroll on new content
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    // Only auto-scroll if already near the bottom
    const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150;
    if (isNearBottom) scrollToBottom();
  }, [messages, currentAssistantMessage, agentPhase, planOverview, executionTasks, fixSteps, followUpSteps, scrollToBottom]);

  // Track scroll position to show/hide the button
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const handleScroll = () => {
      const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      setShowScrollBtn(distFromBottom > 200);
    };
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  // Force scroll to bottom when plan overview appears (including on reconnect)
  useEffect(() => {
    if (agentPhase === 'awaiting_approval' && planOverview) {
      setTimeout(scrollToBottom, 100);
    }
  }, [agentPhase, planOverview, scrollToBottom]);

  // Scroll to bottom on initial history load (after page refresh)
  useEffect(() => {
    if (historyLoaded && messages.length > 0) {
      setTimeout(scrollToBottom, 100);
    }
  }, [historyLoaded, scrollToBottom]);

  const showDesignProgress = agentPhase === 'designing';
  const showOverview = agentPhase === 'awaiting_approval' && planOverview;
  const showTaskProgress = (agentPhase === 'executing' || agentPhase === 'complete') && executionTasks.length > 0;
  const showFixProgress = fixSteps.length > 0 && isStreaming;
  const showFollowUpProgress = followUpSteps.length > 0 && isStreaming;
  const showStreamingMessage = isStreaming && currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress;
  const showPhaseIndicator = agentPhase === 'classifying' || agentPhase === 'planning' || (agentPhase === 'exploring' && followUpSteps.length === 0);
  const showTypingDots = isStreaming && !currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress && !showPhaseIndicator;

  return (
    <div className="flex flex-col h-full overflow-hidden relative">

      {/* Messages */}
      <div ref={scrollContainerRef} className="flex-1 overflow-auto p-4 flex flex-col gap-4 scroll-smooth">
        {isCreating && messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-sm">{t('chat.settingUpProject')}</span>
          </div>
        )}
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

      {/* Scroll to bottom button */}
      {showScrollBtn && (
        <button
          onClick={scrollToBottom}
          className="absolute bottom-[120px] start-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-surface border border-border shadow-[var(--shadow-md)] flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all duration-150 z-10"
          title={t('chat.scrollToBottom')}
        >
          <ArrowDown size={16} />
        </button>
      )}

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
