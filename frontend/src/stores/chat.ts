import { create } from 'zustand';
import type { Message, Action, WSMessage } from '../types';
import { createChatSocket } from '../services/websocket';
import { useSessionStore } from './session';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentAssistantMessage: string;
  actions: Action[];
  sendMessage: (content: string) => void;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  setStreaming: (streaming: boolean) => void;
}

function generateId(): string {
  return crypto.randomUUID();
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentAssistantMessage: '',
  actions: [],

  sendMessage(content: string) {
    const sessionId = useSessionStore.getState().sessionId;
    if (!sessionId) return;

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    set((state) => ({
      messages: [...state.messages, userMessage],
      isStreaming: true,
      currentAssistantMessage: '',
      actions: [],
    }));

    const socket = createChatSocket(sessionId);
    const assistantId = generateId();

    socket.onMessage((msg: WSMessage) => {
      switch (msg.type) {
        case 'text': {
          set((state) => ({
            currentAssistantMessage: state.currentAssistantMessage + msg.content,
          }));
          break;
        }
        case 'file': {
          set((state) => ({
            actions: [
              ...state.actions,
              { type: 'file', path: msg.path, content: msg.content },
            ],
          }));
          break;
        }
        case 'shell_output': {
          set((state) => ({
            actions: [
              ...state.actions,
              { type: 'shell', command: msg.command, output: msg.output },
            ],
          }));
          break;
        }
        case 'action_complete': {
          const state = get();
          const assistantMessage: Message = {
            id: assistantId,
            role: 'assistant',
            content: state.currentAssistantMessage,
            actions: state.actions.length > 0 ? [...state.actions] : undefined,
            timestamp: Date.now(),
          };
          set((s) => ({
            messages: [...s.messages, assistantMessage],
            isStreaming: false,
            currentAssistantMessage: '',
            actions: [],
          }));
          socket.close();
          break;
        }
      }
    });

    socket.send({ type: 'message', content });
  },

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  clearMessages() {
    set({ messages: [], currentAssistantMessage: '', actions: [] });
  },

  setStreaming(streaming: boolean) {
    set({ isStreaming: streaming });
  },
}));
