import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useChatStore } from '../chat';
import { handleVersionMessage } from '../version';
import type { ChatAttachment, WSMessage } from '../../types';

vi.mock('../files', () => ({
  useFilesStore: {
    getState: () => ({ openFiles: new Map(), loadFileTree: vi.fn(), refreshOpenFiles: vi.fn(), saveVersion: 0 }),
  },
}));

vi.mock('../session', () => ({
  useSessionStore: {
    getState: () => ({ projectId: 'proj-1', currentProject: { id: 'proj-1' } }),
  },
}));

vi.mock('../agentAlivePoll', () => ({
  startAgentAlivePolling: vi.fn(),
  stopAgentAlivePolling: vi.fn(),
}));

vi.mock('../../utils/notifications', () => ({ requestPermissionIfNeeded: vi.fn() }));

vi.mock('i18next', () => ({
  default: { t: (key: string, options?: object) => `${key} ${JSON.stringify(options ?? {})}` },
}));

const uploadAttachment = vi.fn();
vi.mock('../../services/api', () => ({
  fetchModels: vi.fn(),
  fetchDefaultModel: vi.fn(),
  fetchAgentEvents: vi.fn(),
  updateProjectModel: vi.fn(() => Promise.resolve()),
  uploadAttachment: (...args: unknown[]) => uploadAttachment(...args),
}));

vi.mock('../../utils/attachments', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../utils/attachments')>()),
  prepareImage: vi.fn(async (file: File) => ({ blob: file, width: 800, height: 600 })),
}));

const socketSend = vi.fn();
vi.mock('../../services/websocket', () => ({
  getChatSocket: () => ({ send: socketSend, onMessage: vi.fn(), offMessage: vi.fn() }),
}));

const SHOT: ChatAttachment = { id: 'up-1', name: 'shot.png', content_type: 'image/png', width: 800, height: 600 };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

describe('chat attachments', () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:preview');
    URL.revokeObjectURL = vi.fn();
    useChatStore.setState({
      messages: [],
      pendingAttachments: [],
      error: null,
      draft: '',
      models: [{ id: 'vision', name: 'Vision', provider: 'p', supports_vision: true }],
      selectedModel: 'vision',
    });
    uploadAttachment.mockReset();
    socketSend.mockClear();
  });

  it('uploads an image, then sends its id with the message and clears the chips', async () => {
    const upload = deferred<ChatAttachment>();
    uploadAttachment.mockReturnValue(upload.promise);

    useChatStore.getState().addAttachments([new File(['png'], 'shot.png', { type: 'image/png' })]);
    await flush();
    expect(useChatStore.getState().pendingAttachments).toMatchObject([{ name: 'shot.png', status: 'uploading' }]);
    expect(uploadAttachment).toHaveBeenCalledWith(
      'proj-1', expect.any(File), expect.objectContaining({ name: 'shot.png', width: 800, height: 600 }),
    );

    upload.resolve(SHOT);
    await flush();
    expect(useChatStore.getState().pendingAttachments).toMatchObject([{ status: 'ready', upload: SHOT }]);

    useChatStore.getState().sendMessage('match this');
    expect(socketSend).toHaveBeenCalledWith(expect.objectContaining({ content: 'match this', attachmentIds: ['up-1'] }));
    expect(useChatStore.getState().messages[0].attachments).toEqual([SHOT]);
    expect(useChatStore.getState().pendingAttachments).toEqual([]);
  });

  it('gives the attachments back when the turn is refused', async () => {
    uploadAttachment.mockResolvedValue(SHOT);
    useChatStore.getState().addAttachments([new File(['png'], 'shot.png', { type: 'image/png' })]);
    await flush();

    useChatStore.getState().sendMessage('match this');
    handleVersionMessage({ type: 'error', message: 'nope' } as unknown as WSMessage);

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().pendingAttachments).toMatchObject([{ status: 'ready', upload: SHOT }]);
  });

  it('marks a failed upload and reports it', async () => {
    uploadAttachment.mockRejectedValue(new Error('boom'));

    useChatStore.getState().addAttachments([new File(['a,b'], 'data.csv', { type: 'text/csv' })]);
    await flush();

    expect(useChatStore.getState().pendingAttachments).toMatchObject([{ name: 'data.csv', status: 'failed' }]);
    expect(useChatStore.getState().error).toContain('data.csv');
  });

  it('refuses unsupported files, and images when the model has no vision', () => {
    useChatStore.setState({ models: [{ id: 'text', name: 'Text', provider: 'p', supports_vision: false }], selectedModel: 'text' });

    useChatStore.getState().addAttachments([new File(['x'], 'page.html', { type: 'text/html' })]);
    expect(useChatStore.getState().error).toContain('page.html');

    useChatStore.getState().addAttachments([new File(['png'], 'shot.png', { type: 'image/png' })]);
    expect(useChatStore.getState().error).toContain('chat.attachment.noVision');

    expect(useChatStore.getState().pendingAttachments).toEqual([]);
    expect(uploadAttachment).not.toHaveBeenCalled();
  });

  it('removing a chip frees its preview', async () => {
    uploadAttachment.mockResolvedValue(SHOT);
    useChatStore.getState().addAttachments([new File(['png'], 'shot.png', { type: 'image/png' })]);
    await flush();

    useChatStore.getState().removeAttachment(useChatStore.getState().pendingAttachments[0].localId);

    expect(useChatStore.getState().pendingAttachments).toEqual([]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');
  });
});
