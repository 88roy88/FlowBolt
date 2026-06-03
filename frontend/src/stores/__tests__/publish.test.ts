import { describe, it, expect, beforeEach } from 'vitest';
import { usePublishStore } from '../publish';

describe('publishStore', () => {
  beforeEach(() => {
    usePublishStore.setState({
      projectId: null,
      mode: 'create',
      isOpen: false,
      slug: '',
      initialSlug: '',
    });
  });

  it('open() initializes create vs edit mode', () => {
    const store = usePublishStore.getState();

    store.open('proj-1');
    expect(usePublishStore.getState().mode).toBe('create');
    expect(usePublishStore.getState().initialSlug).toBe('');
    expect(usePublishStore.getState().isOpen).toBe(true);

    store.open('proj-2', 'my-custom-slug');
    expect(usePublishStore.getState().mode).toBe('edit');
    expect(usePublishStore.getState().initialSlug).toBe('my-custom-slug');
    expect(usePublishStore.getState().slug).toBe('my-custom-slug');
  });

  it('open() treats a handle equal to the projectId as the default (no slug)', () => {
    usePublishStore.getState().open('proj-3', 'proj-3');
    expect(usePublishStore.getState().initialSlug).toBe('');
  });

  it('open() preserves an in-progress draft when reopening the same project', () => {
    const store = usePublishStore.getState();
    store.open('proj-1');
    store.setSlug('draft-slug');
    store.close();
    store.open('proj-1');
    expect(usePublishStore.getState().slug).toBe('draft-slug');
  });

  it('setSlug() formats free text into a candidate slug', () => {
    usePublishStore.getState().setSlug('My Awesome_App!!');
    expect(usePublishStore.getState().slug).toBe('my-awesome-app');
  });

  it('resetSlug() reverts to the initial handle', () => {
    const store = usePublishStore.getState();
    store.open('proj-1', 'initial-one');
    store.setSlug('changed-one');
    store.resetSlug();
    expect(usePublishStore.getState().slug).toBe('initial-one');
  });

  it('isChanged() reflects divergence from the initial handle', () => {
    const store = usePublishStore.getState();
    store.open('proj-1', 'initial-one');
    expect(usePublishStore.getState().isChanged()).toBe(false);
    store.setSlug('changed-one');
    expect(usePublishStore.getState().isChanged()).toBe(true);
  });
});
