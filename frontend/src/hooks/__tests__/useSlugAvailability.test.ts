import { describe, it, expect } from 'vitest';
import { deriveSlugStatus, canPublishSlug } from '../useSlugAvailability';

describe('deriveSlugStatus', () => {
  const settled = (available: boolean) => ({ available });

  it('is idle for an empty slug', () => {
    expect(deriveSlugStatus('', '', '', false, undefined)).toBe('idle');
  });

  it('is invalid when the slug fails the format rule', () => {
    expect(deriveSlugStatus('a', 'a', '', false, undefined)).toBe('invalid');
  });

  it('is idle when the slug equals the initial handle', () => {
    expect(deriveSlugStatus('keep-me', 'keep-me', 'keep-me', false, settled(false))).toBe('idle');
  });

  it('is checking while the debounce has not caught up', () => {
    expect(deriveSlugStatus('my-slug', 'my-slu', '', false, undefined)).toBe('checking');
  });

  it('is checking while the query is fetching', () => {
    expect(deriveSlugStatus('my-slug', 'my-slug', '', true, undefined)).toBe('checking');
  });

  it('reflects availability once the query settles', () => {
    expect(deriveSlugStatus('my-slug', 'my-slug', '', false, settled(true))).toBe('available');
    expect(deriveSlugStatus('my-slug', 'my-slug', '', false, settled(false))).toBe('taken');
  });
});

describe('canPublishSlug', () => {
  it('is false without a slug', () => {
    expect(canPublishSlug('', 'idle', '')).toBe(false);
  });

  it('is true for an available slug', () => {
    expect(canPublishSlug('free-slug', 'available', '')).toBe(true);
  });

  it('is true for an unchanged slug in edit mode (republish)', () => {
    expect(canPublishSlug('keep-me', 'idle', 'keep-me')).toBe(true);
  });

  it('is false for a taken slug', () => {
    expect(canPublishSlug('taken-slug', 'taken', '')).toBe(false);
  });
});
