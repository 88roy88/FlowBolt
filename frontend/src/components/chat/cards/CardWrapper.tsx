import type { CSSProperties, ReactNode } from 'react';

const baseStyle: CSSProperties = {
  background: 'var(--surface)',
  border: '1px solid var(--border)',
  borderRadius: '12px',
  padding: '14px 16px',
  fontSize: '13px',
};

export function CardWrapper({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div style={{ ...baseStyle, ...style }}>{children}</div>;
}
