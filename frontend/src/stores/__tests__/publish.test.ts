import { describe, it, expect, vi, beforeEach } from 'vitest';
import { usePublishStore } from '../publish';
import { checkSlugAvailability, publishToS3 } from '../../services/api';

// Mock API services
vi.mock('../../services/api', () => ({
  checkSlugAvailability: vi.fn(),
  publishToS3: vi.fn(),
}));

// Mock session store actions
const mockSetProjectPublishedUrl = vi.fn();
vi.mock('../../stores/session', () => ({
  useSessionStore: {
    getState: () => ({
      setProjectPublishedUrl: mockSetProjectPublishedUrl,
    }),
  },
}));

describe('publishStore', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    
    // Manually reset store state
    usePublishStore.setState({
      projectId: null,
      mode: 'create',
      isOpen: false,
      slug: '',
      initialSlug: '',
      status: 'idle',
      isPublishing: false,
      resultUrl: null,
      errorMessage: null,
    });
  });

  it('should initialize correctly with open()', () => {
    const store = usePublishStore.getState();
    
    // Create mode (no existingHandle)
    store.open('proj-1');
    expect(usePublishStore.getState().projectId).toBe('proj-1');
    expect(usePublishStore.getState().mode).toBe('create');
    expect(usePublishStore.getState().slug).toBe('');
    expect(usePublishStore.getState().isOpen).toBe(true);

    // Edit mode
    store.open('proj-2', 'my-custom-slug');
    expect(usePublishStore.getState().projectId).toBe('proj-2');
    expect(usePublishStore.getState().mode).toBe('edit');
    expect(usePublishStore.getState().initialSlug).toBe('my-custom-slug');
    expect(usePublishStore.getState().slug).toBe('my-custom-slug');
  });

  it('should format slug and trigger debounced check in setSlug()', async () => {
    const store = usePublishStore.getState();
    store.open('proj-1');
    
    vi.mocked(checkSlugAvailability).mockResolvedValue({ available: true });

    // Typing with weird characters
    store.setSlug('My Awesome App!');
    expect(usePublishStore.getState().slug).toBe('my-awesome-app');
    expect(usePublishStore.getState().status).toBe('checking');

    // Fast typing: advance 200ms
    vi.advanceTimersByTime(200);
    store.setSlug('new-slug');
    expect(usePublishStore.getState().slug).toBe('new-slug');

    // Wait for debounce (500ms)
    vi.advanceTimersByTime(500);
    
    // Verify API called with latest slug
    expect(checkSlugAvailability).toHaveBeenCalledTimes(1);
    expect(checkSlugAvailability).toHaveBeenCalledWith('proj-1', 'new-slug', expect.any(Object));

    // Wait for promise
    await vi.runAllTimersAsync();
    expect(usePublishStore.getState().status).toBe('available');
  });

  it('should handle "already taken" status', async () => {
    const store = usePublishStore.getState();
    store.open('proj-1');
    
    vi.mocked(checkSlugAvailability).mockResolvedValue({ available: false });

    store.setSlug('taken-slug');
    vi.advanceTimersByTime(500);
    await vi.runAllTimersAsync();

    expect(usePublishStore.getState().status).toBe('taken');
  });

  it('should reset slug correctly', () => {
    const store = usePublishStore.getState();
    store.open('proj-1', 'initial-one');
    
    store.setSlug('changed-one');
    expect(usePublishStore.getState().slug).toBe('changed-one');

    store.resetSlug();
    expect(usePublishStore.getState().slug).toBe('initial-one');
    expect(usePublishStore.getState().status).toBe('idle');
  });

  it('should orchestrate publish correctly', async () => {
    const store = usePublishStore.getState();
    store.open('proj-1', 'existing');
    
    const mockResult = { url: '/shared/existing', handle: 'existing', published_at: '2021-01-01' };
    vi.mocked(publishToS3).mockResolvedValue(mockResult);
    
    await store.performPublish(true);

    expect(publishToS3).toHaveBeenCalledWith('proj-1', 'existing');
    expect(mockSetProjectPublishedUrl).toHaveBeenCalledWith('proj-1', 'existing', '2021-01-01');
    expect(usePublishStore.getState().resultUrl).toBe('/shared/existing');
    expect(usePublishStore.getState().isPublishing).toBe(false);
  });

  it('should handle publish errors', async () => {
    const store = usePublishStore.getState();
    store.open('proj-1');
    
    vi.mocked(publishToS3).mockRejectedValue(new Error('S3 Error'));

    await store.performPublish(false); // Use default link

    expect(usePublishStore.getState().errorMessage).toBe('S3 Error');
    expect(usePublishStore.getState().isPublishing).toBe(false);
  });
});
