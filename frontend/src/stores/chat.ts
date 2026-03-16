import { create } from 'zustand';
import type { Message, Action, WSMessage, AIModel } from '../types';
import { getChatSocket } from '../services/websocket';
import { useSessionStore } from './session';
import { useFilesStore } from './files';
import { fetchModels, fetchDefaultModel } from '../services/api';

interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  currentAssistantMessage: string;
  actions: Action[];
  error: string | null;
  models: AIModel[];
  selectedModel: string | null;
  sendMessage: (content: string) => void;
  addMessage: (message: Message) => void;
  clearMessages: () => void;
  clearError: () => void;
  setStreaming: (streaming: boolean) => void;
  setSelectedModel: (model: string) => void;
  loadModels: () => Promise<void>;
}

function generateId(): string {
  return crypto.randomUUID();
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentAssistantMessage: '',
  actions: [],
  error: null,
  models: [],
  selectedModel: null,

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
      error: null,
    }));

    const socket = getChatSocket(sessionId);
    const assistantId = generateId();

    const handler = (msg: WSMessage) => {
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
          // Update the file in editor if it's open, and refresh tree
          const filesStore = useFilesStore.getState();
          if (filesStore.openFiles.has(msg.path)) {
            filesStore.updateFileContent(msg.path, msg.content);
          }
          filesStore.loadFileTree();
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
        case 'error': {
          set({ error: msg.message, isStreaming: false });
          socket.offMessage(handler);
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
          socket.offMessage(handler);
          // Refresh file tree after all actions are done
          useFilesStore.getState().loadFileTree();
          break;
        }
      }
    };

    socket.onMessage(handler);

    const { selectedModel } = get();
    const msg: WSMessage = selectedModel
      ? { type: 'message', content, model: selectedModel }
      : { type: 'message', content };
    socket.send(msg);
  },

  addMessage(message: Message) {
    set((state) => ({ messages: [...state.messages, message] }));
  },

  clearMessages() {
    set({ messages: [], currentAssistantMessage: '', actions: [], error: null });
  },

  clearError() {
    set({ error: null });
  },

  setStreaming(streaming: boolean) {
    set({ isStreaming: streaming });
  },

  setSelectedModel(model: string) {
    set({ selectedModel: model });
  },

  async loadModels() {
    try {
      const [models, defaultModel] = await Promise.all([
        fetchModels(),
        fetchDefaultModel(),
      ]);
      // Ensure the default model is in the list even if the provider didn't return it
      const modelIds = new Set(models.map((m) => m.id));
      if (defaultModel && !modelIds.has(defaultModel)) {
        models.unshift({ id: defaultModel, name: defaultModel, provider: 'default' });
      }
      set((state) => ({
        models,
        selectedModel: state.selectedModel ?? defaultModel,
      }));
    } catch (err) {
      console.error('Failed to load models:', err);
    }
  },
}));
