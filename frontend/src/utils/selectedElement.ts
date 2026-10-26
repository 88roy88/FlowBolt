import type { SelectedElement } from '../types';

const LIMITS = { tag: 40, selector: 300, text: 120, classes: 200, html: 600, component: 80 } as const;
const MAX_COMPONENTS = 4;
const LABEL_TEXT_MAX = 30;

function clip(value: unknown, max: number): string {
  return typeof value === 'string' ? value.slice(0, max) : '';
}

export function parseSelectedElement(raw: unknown): Omit<SelectedElement, 'id'> | null {
  if (!raw || typeof raw !== 'object') return null;
  const r = raw as Record<string, unknown>;
  const tag = clip(r.tag, LIMITS.tag).toLowerCase();
  if (!tag) return null;
  return {
    tag,
    selector: clip(r.selector, LIMITS.selector),
    text: clip(r.text, LIMITS.text),
    classes: clip(r.classes, LIMITS.classes),
    html: clip(r.html, LIMITS.html),
    components: Array.isArray(r.components)
      ? r.components
          .filter((c): c is string => typeof c === 'string' && c.length > 0)
          .slice(0, MAX_COMPONENTS)
          .map((c) => c.slice(0, LIMITS.component))
      : [],
  };
}

export function elementLabel(el: Omit<SelectedElement, 'id'>): string {
  const text = el.text.replace(/\s+/g, ' ').trim();
  if (text) return text.length > LABEL_TEXT_MAX ? `${text.slice(0, LABEL_TEXT_MAX)}…` : text;
  const firstClass = el.classes.trim().split(/\s+/)[0];
  if (firstClass) return `.${firstClass}`;
  return el.tag;
}

export function elementTooltip(el: Omit<SelectedElement, 'id'>): string {
  return [el.components.join(' < '), el.selector].filter(Boolean).join(' · ');
}
