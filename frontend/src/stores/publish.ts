import { create } from 'zustand';
import type { PublishDetails } from '../types';

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

  appType: string;
  appDescription: string;
  publishReason: string;

  open: (projectId: string, existingHandle?: string, saved?: PublishDetails) => void;
  close: () => void;
  setSlug: (val: string) => void;
  resetSlug: () => void;
  setAppType: (val: string) => void;
  setAppDescription: (val: string) => void;
  setPublishReason: (val: string) => void;

  isChanged: () => boolean;
}

export const usePublishStore = create<PublishState>((set, get) => ({
  projectId: null,
  mode: 'create',
  isOpen: false,
  slug: '',
  initialSlug: '',
  appType: '',
  appDescription: '',
  publishReason: '',

  open(projectId, existingHandle, saved) {
    const isDefaultHandle = existingHandle === projectId;
    const initialSlug = isDefaultHandle ? '' : (existingHandle ?? '');
    const sameProject = get().projectId === projectId;
    set({
      projectId,
      mode: existingHandle ? 'edit' : 'create',
      initialSlug,
      // Preserve an in-progress draft when reopening the same project.
      slug: sameProject ? get().slug : initialSlug,
      appType: sameProject ? get().appType : (saved?.app_type ?? ''),
      appDescription: sameProject ? get().appDescription : (saved?.app_description ?? ''),
      publishReason: sameProject ? get().publishReason : (saved?.publish_reason ?? ''),
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

  setAppType(appType) {
    set({ appType });
  },

  setAppDescription(appDescription) {
    set({ appDescription });
  },

  setPublishReason(publishReason) {
    set({ publishReason });
  },

  isChanged() {
    const { slug, initialSlug } = get();
    return slug !== initialSlug;
  },
}));
