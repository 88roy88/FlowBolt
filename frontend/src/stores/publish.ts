import { create } from 'zustand';

// UX mirror of backend _SLUG_RE (api/publish.py) — keep in sync.
export const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

// Must match backend `/shared/{handle}`, nginx, and the vite proxy.
export const SHARED_PREFIX = '/shared/';

interface PublishState {
  projectId: string | null;
  mode: 'create' | 'edit';
  isOpen: boolean;

  slug: string;
  initialSlug: string;

  open: (projectId: string, existingHandle?: string) => void;
  close: () => void;
  setSlug: (val: string) => void;
  resetSlug: () => void;

  isChanged: () => boolean;
}

export const usePublishStore = create<PublishState>((set, get) => ({
  projectId: null,
  mode: 'create',
  isOpen: false,
  slug: '',
  initialSlug: '',

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
      isOpen: true,
    });
  },

  close() {
    set({ isOpen: false });
  },

  setSlug(val) {
    const formatted = val
      .toLowerCase()
      .replace(/[\s_]+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-');
    set({ slug: formatted });
  },

  resetSlug() {
    set({ slug: get().initialSlug });
  },

  isChanged() {
    const { slug, initialSlug } = get();
    return slug !== initialSlug;
  },
}));
