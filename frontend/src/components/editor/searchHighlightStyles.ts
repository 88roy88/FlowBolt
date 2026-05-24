const STYLE_ID = 'editor-search-hit-highlight-style';

export function ensureEditorSearchHitHighlightStyles(): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = `
      .editor-search-hit-highlight-inline {
        background: rgba(255, 211, 77, 0.35);
        border-radius: 2px;
      }
      .editor-search-hit-highlight-line {
        background: rgba(255, 211, 77, 0.08);
      }
    `;
  document.head.appendChild(style);
}
