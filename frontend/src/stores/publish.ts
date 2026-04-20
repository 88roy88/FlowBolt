import { create } from 'zustand';
import { checkSlugAvailability, publishToS3 } from '../services/api';
import { useSessionStore } from './session';
import { DebouncedAction } from '../utils/concurrency';

export type SlugStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

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
    // Determine mode
    const mode = existingHandle ? 'edit' : 'create';
    
    // Determine initial slug
    const isDefaultHandle = existingHandle === projectId;
    const initialSlug = isDefaultHandle ? '' : (existingHandle ?? '');

    const current = get();
    
    // If we're already open for this project, just show it.
    // Otherwise, initialize/reset.
    if (current.projectId !== projectId || !current.isOpen) {
      set({
        projectId,
        mode,
        initialSlug,
        slug: current.projectId === projectId ? current.slug : initialSlug,
        status: current.projectId === projectId ? current.status : 'idle',
        isPublishing: false,
        resultUrl: null,
        errorMessage: null,
        isOpen: true,
      });
    }
  },

  close() {
    checker.cancel();
    set({ isOpen: false });
  },

  setSlug(val) {
    const formatted = val.toLowerCase().replace(/[^a-z0-9-]/g, '');
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
    const { projectId, slug, isPublishing, initialSlug, status } = get();
    if (!projectId || isPublishing) return;
    
    if (useSlug) {
      const canDo = slug !== '' && (status === 'available' || slug === initialSlug);
      if (!canDo) return;
    }

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
