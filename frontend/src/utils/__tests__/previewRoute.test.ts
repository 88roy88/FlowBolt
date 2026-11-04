import { describe, it, expect } from 'vitest';
import { formatPreviewRoute } from '../previewRoute';

describe('formatPreviewRoute', () => {
  it('keeps plain routes with their query and hash', () => {
    expect(formatPreviewRoute('/')).toBe('/');
    expect(formatPreviewRoute('/users/42?tab=info#top')).toBe('/users/42?tab=info#top');
  });

  it('unwraps HashRouter routes', () => {
    expect(formatPreviewRoute('/#/')).toBe('/');
    expect(formatPreviewRoute('/#/settings')).toBe('/settings');
  });

  it('leaves in-page anchors on the home page alone', () => {
    expect(formatPreviewRoute('/#pricing')).toBe('/#pricing');
  });

  it('decodes escaped characters', () => {
    expect(formatPreviewRoute('/%D7%A9%D7%9C%D7%95%D7%9D')).toBe('/שלום');
  });

  it('returns malformed escapes as they are', () => {
    expect(formatPreviewRoute('/100%')).toBe('/100%');
  });
});
