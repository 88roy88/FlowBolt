import { describe, it, expect } from 'vitest';
import { withAppTitle } from '../appTitle';

describe('withAppTitle', () => {
  it('replaces only the title', () => {
    const html = '<head><title>App</title><script>var a = 1;</script></head><body></body>';
    expect(withAppTitle(html, 'Shop')).toBe('<head><title>Shop</title><script>var a = 1;</script></head><body></body>');
  });

  it('keeps attributes and handles multi-line titles', () => {
    expect(withAppTitle('<TITLE lang="en">\n  App\n</TITLE>', 'Shop')).toBe('<TITLE lang="en">Shop</title>');
  });

  it('escapes HTML in the title', () => {
    expect(withAppTitle('<title>App</title>', 'R&D </title><script>')).toBe(
      '<title>R&amp;D &lt;/title&gt;&lt;script&gt;</title>',
    );
  });

  it('keeps dollar signs literal', () => {
    expect(withAppTitle('<title>App</title>', '$1 costs $2')).toBe('<title>$1 costs $2</title>');
    expect(withAppTitle('<head></head>', '$1')).toBe('<head><title>$1</title></head>');
  });

  it('adds a title to a head without one', () => {
    expect(withAppTitle('<head><meta charset="utf-8"></head>', 'Shop')).toBe(
      '<head><meta charset="utf-8"><title>Shop</title></head>',
    );
  });

  it('throws when there is nowhere to put the title', () => {
    expect(() => withAppTitle('<body></body>', 'Shop')).toThrow();
  });
});
