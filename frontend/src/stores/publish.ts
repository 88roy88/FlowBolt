import { create } from 'zustand';
import { checkSlugAvailability, publishToS3 } from '../services/api';
import { useSessionStore } from './session';
import { DebouncedAction } from '../utils/concurrency';

export type SlugStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

// UX mirror of backend _SLUG_RE (api/publish.py) — keep in sync.
const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

// Public path prefix — must match backend `/shared/{handle}`, nginx, and the vite proxy.
export const SHARED_PREFIX = '/shared/';

const checker = new DebouncedAction();

interface PublishState {
  // Config
  projectId: string | null;
  mode: 'create' | 'edit';
  
  // Visibility
  isOpen: boolean;
  
  // Input State
  slug: string;
  initialSlug: string;
  status: SlugStatus;
  
  // Results
  isPublishing: boolean;
  resultUrl: string | null;
  errorMessage: string | null;

  // Actions
  open: (projectId: string, existingHandle?: string) => void;
  close: () => void;
  setSlug: (val: string) => void;
  resetSlug: () => void;
  performPublish: (useSlug: boolean) => Promise<void>;
  
  // Computed (accessed via helpers)
  canPublish: () => boolean;
  isChanged: () => boolean;
}

export const usePublishStore = create<PublishState>((set, get) => ({
  projectId: null,
  mode: 'create',
  isOpen: false,
  slug: '',
  initialSlug: '',
  status: 'idle',
  isPublishing: false,
  resultUrl: null,
  errorMessage: null,

  open(projectId, existingHandle) {
    const isDefaultHandle = existingHandle === projectId;
    const initialSlug = isDefaultHandle ? '' : (existingHandle ?? '');
    const sameProject = get().projectId === projectId;
    set({
      projectId,
      mode: existingHandle ? 'edit' : 'create',
      initialSlug,
      // Preserve an in-progress draft when reopening the same project.
      slug: sameProject ? get().slug : initialSlug,
      status: sameProject ? get().status : 'idle',
      isPublishing: false,
      resultUrl: null,
      errorMessage: null,
      isOpen: true,
    });
  },

  close() {
    checker.cancel();
    set({ isOpen: false });
  },

  setSlug(val) {
    // Replace spaces and underscores with hyphens, then strip non-slug chars
    const formatted = val
      .toLowerCase()
      .replace(/[\s_]+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-');
    
    const { initialSlug, projectId } = get();

    set({ slug: formatted });
    checker.cancel();

    if (!formatted) {
      set({ status: 'idle' });
      return;
    }

    if (!SLUG_RE.test(formatted)) {
      set({ status: 'invalid' });
      return;
    }

    if (formatted === initialSlug) {
      set({ status: 'idle' });
      return;
    }

    set({ status: 'checking' });

    checker.schedule(500, async (signal) => {
      if (!projectId) return;
      
      const { available } = await checkSlugAvailability(projectId, formatted, { signal });
      set({ status: available ? 'available' : 'taken' });
    });
  },

  resetSlug() {
    checker.cancel();
    const { initialSlug } = get();
    set({ slug: initialSlug, status: 'idle', errorMessage: null });
  },

  async performPublish(useSlug: boolean) {
    const { projectId, slug, isPublishing } = get();
    if (!projectId || isPublishing) return;
    if (useSlug && !get().canPublish()) return;

    set({ isPublishing: true, errorMessage: null });
    try {
      const result = await publishToS3(projectId, useSlug ? slug : undefined);
      useSessionStore.getState().setProjectPublishedUrl(projectId, result.handle, result.published_at);
      set({ resultUrl: result.url });
    } catch (err) {
      set({ errorMessage: err instanceof Error ? err.message : String(err) });
    } finally {
      set({ isPublishing: false });
    }
  },

  canPublish() {
    const { slug, status, initialSlug } = get();
    return slug !== '' && (status === 'available' || slug === initialSlug);
  },

  isChanged() {
    const { slug, initialSlug } = get();
    return slug !== initialSlug;
  },
}));
