import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDown } from 'lucide-react';
import { formatDayDivider, sameDay } from '../../utils/formatTime';
import type { Message } from '../../types';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive } from '../../stores/chatAgentState';
import { ChatMessage } from './ChatMessage';
import { PromptInput } from './PromptInput';
import { WorkPlanView } from './WorkPlanView';
import { InterviewCard } from './InterviewCard';
import { TaskProgress } from './TaskProgress';
import { PhaseIndicator } from './PhaseIndicator';
import { DesignProgress } from './DesignProgress';
import { FixProgressCard } from './cards/FixProgressCard';
import { FollowUpProgress } from './cards/FollowUpProgress';

type DayGroup = { key: string; ts: number; msgs: Message[] };

function groupMessagesByDay(messages: Message[]): DayGroup[] {
  return messages.reduce<DayGroup[]>((groups, msg) => {
    const last = groups.at(-1);
    if (last && sameDay(last.ts, msg.timestamp)) last.msgs.push(msg);
    else groups.push({ key: msg.id, ts: msg.timestamp, msgs: [msg] });
    return groups;
  }, []);
}

function DayDivider({ label }: { label: string }) {
  return (
    <div className="sticky top-0 z-10 flex justify-center pointer-events-none">
      <span className="pointer-events-auto text-[11px] text-muted-foreground bg-surface border border-border rounded-full px-2.5 py-0.5 shadow-[var(--shadow-sm)] select-none">
        {label}
      </span>
    </div>
  );
}

export function ChatPanel() {
  const { t, i18n } = useTranslation();
  const {
    messages, currentAssistantMessage, actions, error, clearError,
    agentPhase, planOverview, interviewQuestions, executionTasks, designProgress, fixSteps, followUpSteps, fileDiffs,
  } = useChatStore();
  const agentActive = useChatStore(isAgentAlive);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const [showScrollBtn, setShowScrollBtn] = useState(false);

  const pinToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  const observeContentForPinning = useCallback((node: HTMLDivElement | null) => {
    if (!node) return;
    const observer = new ResizeObserver(() => {
      if (stickToBottomRef.current) pinToBottom();
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [pinToBottom]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distFromBottom < 150;
    setShowScrollBtn(distFromBottom > 200);
  };

  const jumpToBottom = () => {
    stickToBottomRef.current = true;
    scrollContainerRef.current?.scrollTo({ top: scrollContainerRef.current.scrollHeight, behavior: 'smooth' });
  };

  const wasAgentActiveRef = useRef(agentActive);
  useEffect(() => {
    const runJustStarted = agentActive && !wasAgentActiveRef.current;
    if (runJustStarted) {
      stickToBottomRef.current = true;
      pinToBottom();
    }
    wasAgentActiveRef.current = agentActive;
  }, [agentActive, pinToBottom]);

  const showDesignProgress = agentPhase === 'designing';
  const showOverview = agentPhase === 'awaiting_approval' && planOverview;
  const showInterview = agentPhase === 'awaiting_interview' && interviewQuestions && interviewQuestions.length > 0;
  const showTaskProgress = (agentPhase === 'executing' || agentPhase === 'complete') && executionTasks.length > 0;
  const showFixProgress = fixSteps.length > 0 && agentActive;
  const showFollowUpProgress = followUpSteps.length > 0 && agentActive;
  const showAgentCard = showDesignProgress || showOverview || showInterview || showTaskProgress || showFixProgress || showFollowUpProgress;
  const showStreamingMessage = agentActive && currentAssistantMessage && !showAgentCard;
  const showPhaseIndicator = agentPhase === 'planning' || agentPhase === 'interviewing' || (agentPhase === 'exploring' && followUpSteps.length === 0);
  const showTypingDots = agentActive && !currentAssistantMessage && !showAgentCard && !showPhaseIndicator;

  const dayGroups = groupMessagesByDay(messages);

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      {/* Messages */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-auto p-4">
        <div ref={observeContentForPinning} className="flex flex-col gap-4">
        {dayGroups.map((group) => (
          <div key={group.key} className="flex flex-col gap-4">
            <DayDivider label={formatDayDivider(group.ts, i18n.language, t)} />
            {group.msgs.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
          </div>
        ))}

        {showPhaseIndicator && <PhaseIndicator phase={agentPhase} />}
        {showDesignProgress && <DesignProgress designProgress={designProgress} />}
        {showOverview && planOverview && <WorkPlanView overview={planOverview} />}
        {showInterview && interviewQuestions && <InterviewCard questions={interviewQuestions} />}
        {showTaskProgress && <TaskProgress tasks={executionTasks} />}
        {showFixProgress && <FixProgressCard steps={fixSteps} content={currentAssistantMessage} diffs={fileDiffs} isLive />}
        {showFollowUpProgress && (
          <FollowUpProgress
            steps={followUpSteps}
            answer={currentAssistantMessage || undefined}
            filesChanged={actions.filter((a) => a.type === 'file' && a.path).map((a) => a.path!)}
            diffs={fileDiffs}
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

        </div>
      </div>

      {/* Scroll to bottom button */}
      {showScrollBtn && (
        <button
          onClick={jumpToBottom}
          className="absolute bottom-[120px] start-1/2 -translate-x-1/2 w-8 h-8 rounded-full bg-surface border border-primary/30 shadow-[var(--shadow-md)] flex items-center justify-center text-primary/70 hover:text-primary hover:bg-primary/10 transition-all duration-150 z-10"
          title={t('chat.scrollToBottom')}
        >
          <ArrowDown size={16} />
        </button>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-center justify-between px-4 py-2 bg-warning/10 border-t border-warning text-warning text-[13px] shrink-0">
          <span>{error}</span>
          <button onClick={clearError} className="text-warning px-1.5 py-0.5 text-xs">
            Dismiss
          </button>
        </div>
      )}

      <PromptInput />
    </div>
  );
}
