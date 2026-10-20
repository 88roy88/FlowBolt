import { describe, expect, it } from 'vitest';
import { elementLabel, elementTooltip, parseSelectedElement } from '../selectedElement';

const BUTTON = {
  tag: 'button', selector: 'main > button.cta', text: 'Sign up', classes: 'cta px-4', html: '<button>Sign up</button>', components: ['PricingCard', 'App'],
};

describe('parseSelectedElement', () => {
  it('accepts a valid element', () => {
    expect(parseSelectedElement(BUTTON)).toEqual(BUTTON);
  });

  it('rejects junk and missing tags', () => {
    expect(parseSelectedElement(null)).toBeNull();
    expect(parseSelectedElement('button')).toBeNull();
    expect(parseSelectedElement({ ...BUTTON, tag: 3 })).toBeNull();
  });

  it('clips long fields and drops bad components', () => {
    const parsed = parseSelectedElement({ ...BUTTON, html: 'x'.repeat(5000), components: ['A', 2, '', 'B', 'C', 'D', 'E'] });
    expect(parsed?.html).toHaveLength(600);
    expect(parsed?.components).toEqual(['A', 'B', 'C', 'D']);
  });
});

describe('elementLabel', () => {
  it('prefers visible text', () => {
    expect(elementLabel(BUTTON)).toBe('Sign up');
  });

  it('truncates long text', () => {
    expect(elementLabel({ ...BUTTON, text: 'a'.repeat(40) })).toBe(`${'a'.repeat(30)}…`);
  });

  it('falls back to the first class, then the tag', () => {
    expect(elementLabel({ ...BUTTON, text: '' })).toBe('.cta');
    expect(elementLabel({ ...BUTTON, text: '', classes: '' })).toBe('button');
  });
});

describe('elementTooltip', () => {
  it('joins components and selector', () => {
    expect(elementTooltip(BUTTON)).toBe('PricingCard < App · main > button.cta');
  });
});
