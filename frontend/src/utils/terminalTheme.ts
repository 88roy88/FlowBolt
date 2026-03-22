import type { Terminal } from '@xterm/xterm';

export function getTerminalTheme(): Terminal['options']['theme'] {
  if (typeof window === 'undefined') return undefined;
  const isLight = document.documentElement.dataset.theme === 'light';
  const styles = getComputedStyle(document.documentElement);
  const bg = styles.getPropertyValue('--bg').trim() || '#1e1e2e';
  const fg = styles.getPropertyValue('--text').trim() || '#cdd6f4';
  const accent = styles.getPropertyValue('--accent').trim() || '#89b4fa';

  return {
    background: bg,
    foreground: fg,
    cursor: accent,
    cursorAccent: bg,
    selectionBackground: isLight ? 'rgba(37, 99, 235, 0.2)' : 'rgba(137, 180, 250, 0.25)',
    selectionForeground: fg,
    black:   isLight ? '#6b7280' : '#45475a',
    brightBlack: isLight ? '#9ca3af' : '#585b70',
    red:     isLight ? '#dc2626' : '#f38ba8',
    brightRed: isLight ? '#ef4444' : '#f38ba8',
    green:   isLight ? '#16a34a' : '#a6e3a1',
    brightGreen: isLight ? '#22c55e' : '#a6e3a1',
    yellow:  isLight ? '#ca8a04' : '#f9e2af',
    brightYellow: isLight ? '#eab308' : '#f9e2af',
    blue:    isLight ? '#2563eb' : '#89b4fa',
    brightBlue: isLight ? '#3b82f6' : '#89b4fa',
    magenta: isLight ? '#9333ea' : '#cba6f7',
    brightMagenta: isLight ? '#a855f7' : '#cba6f7',
    cyan:    isLight ? '#0891b2' : '#94e2d5',
    brightCyan: isLight ? '#06b6d4' : '#94e2d5',
    white:   isLight ? '#374151' : '#bac2de',
    brightWhite: isLight ? '#111827' : '#cdd6f4',
  };
}
