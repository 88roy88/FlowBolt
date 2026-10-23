import { useEffect } from 'react';
import { useSessionStore } from '../stores/session';
import { useChatStore } from '../stores/chat';
import { isAwaitingPlanApproval } from '../stores/chatAgentState';
import { workspaceLocked } from '../stores/workspaceLock';
import { WRITE_ROLES } from '../types';
import { parseSelectedElement } from '../utils/selectedElement';

/** Matches backend `static/preview_toolbar.js`. */
const TOOLBAR_SOURCE = 'buildapp-toolbar';
const BUILDER_SOURCE = 'buildapp-builder';

/** Adds elements picked in the preview (iframe or opened tab) to the chat input, and sends prompts written there. */
export function usePreviewToolbarBridge() {
  const projectId = useSessionStore((s) => s.projectId);

  useEffect(() => {
    if (!projectId) return;

    function onMessage(event: MessageEvent) {
      const data = event.data;
      if (event.origin !== window.location.origin) return;
      if (!data || data.source !== TOOLBAR_SOURCE || data.projectId !== projectId) return;
      const reply = event.source as Window | null;
      if (!reply) return;
      const send = (msg: Record<string, unknown>) =>
        reply.postMessage({ source: BUILDER_SOURCE, ...msg }, window.location.origin);

      const role = useSessionStore.getState().currentProject?.role;
      const canWrite = !role || WRITE_ROLES.has(role);
      const chat = useChatStore.getState();

      if (data.type === 'hello') {
        send({ type: 'ready', canWrite, count: chat.selectedElements.length });
      } else if (data.type === 'element-picked' && canWrite) {
        const element = parseSelectedElement(data.element);
        if (!element) return;
        const added = chat.addSelectedElement({ ...element, id: crypto.randomUUID() });
        send({ type: 'count', count: useChatStore.getState().selectedElements.length, added });
      } else if (data.type === 'clear-elements' && canWrite) {
        chat.clearSelectedElements();
      } else if (data.type === 'send-prompt') {
        const content = typeof data.content === 'string' ? data.content.trim() : '';
        const count = chat.selectedElements.length;
        if (!canWrite) {
          send({ type: 'prompt-result', ok: false, reason: 'readonly', count });
        } else if (!content) {
          send({ type: 'prompt-result', ok: false, reason: 'empty', count });
        } else if (
          // Same gate as the chat input.
          workspaceLocked() !== null ||
          isAwaitingPlanApproval(chat) ||
          useSessionStore.getState().isCreating
        ) {
          send({ type: 'prompt-result', ok: false, reason: 'busy', count });
        } else {
          chat.sendMessage(content, { keepDraft: true });
          send({ type: 'prompt-result', ok: true, count: useChatStore.getState().selectedElements.length });
        }
      }
    }

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [projectId]);
}
