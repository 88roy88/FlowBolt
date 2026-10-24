import { useRef, useState, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowDown, RotateCcw } from 'lucide-react';
import { formatDayDivider, sameDay } from '../../utils/formatTime';
import type { Message } from '../../types';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive, isAwaitingPlanApproval } from '../../stores/chatAgentState';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { Button } from '../ui/button';
import { Dialog, DialogClose, DialogContent, DialogTitle } from '../ui/dialog';
import { ChatMessage } from './ChatMessage';
import { UnsavedEditsRow } from '../version/UnsavedEditsRow';
import { PromptInput } from './PromptInput';
import { WorkPlanView } from './WorkPlanView';
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

const isEditCard = (m: Message) => m.agentCard?.type === 'user_edit';

/** Which messages can be edited, and which user message each regenerate button reruns. */
function rewindTargets(messages: Message[]) {
  const editable = new Set<string>();
  const regenerates = new Map<string, string>();
  let turn: Message | null = null;
  messages.forEach((m, i) => {
    if (isEditCard(m)) return;
    if (m.role === 'user') {
      turn = m.editable ? m : null;
      if (turn && !turn.agentCard) editable.add(m.id);
    }
    const next = messages.slice(i + 1).find((n) => !isEditCard(n));
    if (turn && (!next || next.role === 'user')) regenerates.set(m.id, turn.id);
  });
  return { editable, regenerates };
}

function laterMessages(messages: Message[], id: string): number {
  const idx = messages.findIndex((m) => m.id === id);
  const nextTurn = messages.findIndex((m, i) => i > idx && (m.role === 'user' || isEditCard(m)));
  return nextTurn < 0 ? 0 : messages.length - nextTurn;
}

type Rewind = { id: string; content?: string };

function RewindDialog({ rewind, count, onConfirm, onClose }: {
  rewind: Rewind | null; count: number; onConfirm: () => void; onClose: () => void;
}) {
  const { t } = useTranslation();
  const edit = rewind?.content !== undefined;
  return (
    <Dialog open={rewind !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent>
        <DialogClose onClose={onClose} />
        <DialogTitle>{t(edit ? 'chat.rewind.editTitle' : 'chat.rewind.regenerateTitle')}</DialogTitle>
        <div className="text-sm text-muted-foreground mt-2 mb-4">{t('chat.rewind.body', { count })}</div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="warning" size="sm" onClick={onConfirm}>
            <RotateCcw size={13} />
            {t(edit ? 'chat.rewind.confirmEdit' : 'chat.rewind.confirmRegenerate')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
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
    agentPhase, planOverview, executionTasks, designProgress, fixSteps, followUpSteps, fileDiffs,
  } = useChatStore();
  const agentActive = useChatStore(isAgentAlive);
  const awaitingPlan = useChatStore(isAwaitingPlanApproval);
  const rewindTurn = useChatStore((s) => s.rewindTurn);
  const { lock } = useWorkspaceLock();
  const [pendingRewind, setPendingRewind] = useState<Rewind | null>(null);
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

  const handleClickCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('[aria-expanded]')) stickToBottomRef.current = false;
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
  const showTaskProgress = (agentPhase === 'executing' || agentPhase === 'complete') && executionTasks.length > 0;
  const showFixProgress = fixSteps.length > 0 && agentActive;
  const showFollowUpProgress = followUpSteps.length > 0 && agentActive;
  const showStreamingMessage = agentActive && currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress;
  const showPhaseIndicator = agentPhase === 'planning' || (agentPhase === 'exploring' && followUpSteps.length === 0);
  const showTypingDots = agentActive && !currentAssistantMessage && !showDesignProgress && !showOverview && !showTaskProgress && !showFixProgress && !showFollowUpProgress && !showPhaseIndicator;

  const dayGroups = groupMessagesByDay(messages);
  const canRewind = lock === null && !awaitingPlan;
  const { editable, regenerates } = rewindTargets(messages);

  const requestRewind = (rewind: Rewind) => {
    if (laterMessages(messages, rewind.id) > 0) setPendingRewind(rewind);
    else rewindTurn(rewind.id, rewind.content);
  };
  const confirmRewind = () => {
    if (pendingRewind) rewindTurn(pendingRewind.id, pendingRewind.content);
    setPendingRewind(null);
  };

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      {/* Messages */}
      <div ref={scrollContainerRef} onScroll={handleScroll} onClickCapture={handleClickCapture} className="flex-1 overflow-y-auto overflow-x-hidden p-4">
        <div ref={observeContentForPinning} className="flex flex-col gap-4">
        {dayGroups.map((group) => (
          <div key={group.key} className="flex flex-col gap-4">
            <DayDivider label={formatDayDivider(group.ts, i18n.language, t)} />
            {group.msgs.map((msg) => {
              const turnId = regenerates.get(msg.id);
              return (
                <ChatMessage
                  key={msg.id}
                  message={msg}
                  onEdit={canRewind && editable.has(msg.id) ? (content) => requestRewind({ id: msg.id, content }) : undefined}
                  onRegenerate={canRewind && turnId ? () => requestRewind({ id: turnId }) : undefined}
                />
              );
            })}
          </div>
        ))}

        {showPhaseIndicator && <PhaseIndicator phase={agentPhase} />}
        {showDesignProgress && <DesignProgress designProgress={designProgress} />}
        {showOverview && planOverview && <WorkPlanView overview={planOverview} />}
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

        <UnsavedEditsRow />

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

      <RewindDialog
        rewind={pendingRewind}
        count={pendingRewind ? laterMessages(messages, pendingRewind.id) : 0}
        onConfirm={confirmRewind}
        onClose={() => setPendingRewind(null)}
      />
    </div>
  );
}
