import { useTranslation } from 'react-i18next';
import { ArrowUp, X } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { isAwaitingUserInput } from '../../stores/chatAgentState';
import { useWorkspaceLock } from '../../stores/workspaceLock';

export function QueuedMessages() {
  const { t } = useTranslation();
  const queuedMessages = useChatStore((s) => s.queuedMessages);
  const removeQueued = useChatStore((s) => s.removeQueued);
  const sendQueued = useChatStore((s) => s.sendQueued);
  const awaitingInput = useChatStore(isAwaitingUserInput);
  const { lock } = useWorkspaceLock();

  if (queuedMessages.length === 0) return null;

  // Normally the queue sends itself; this restarts it after a failure or a missed run_released.
  const canSendNow = lock === null && !awaitingInput;

  return (
    <ul className="flex flex-col gap-1 mb-2" aria-label={t('chat.queue.title')} data-testid="queued-messages">
      {queuedMessages.map((m) => (
        <li key={m.id} className="flex items-center gap-1 ps-3 pe-1 py-1 rounded-lg bg-muted/50 text-sm">
          <span className="flex-1 min-w-0 truncate" dir="auto" title={m.content}>{m.content}</span>
          {canSendNow && (
            <button
              onClick={() => sendQueued(m.id)}
              data-testid="queued-send"
              className="flex items-center justify-center w-6 h-6 rounded-full shrink-0 text-primary hover:bg-primary/20"
              title={t('chat.queue.send')}
            >
              <ArrowUp size={14} />
            </button>
          )}
          <button
            onClick={() => removeQueued(m.id)}
            data-testid="queued-remove"
            className="flex items-center justify-center w-6 h-6 rounded-full shrink-0 text-muted-foreground hover:bg-muted"
            title={t('chat.queue.remove')}
          >
            <X size={14} />
          </button>
        </li>
      ))}
    </ul>
  );
}
