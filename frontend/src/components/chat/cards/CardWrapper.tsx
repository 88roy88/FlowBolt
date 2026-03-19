import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type AccentColor = 'primary' | 'success' | 'warning' | 'destructive';

const accentClasses: Record<AccentColor, string> = {
  primary: 'border-l-[3px] border-l-primary',
  success: 'border-l-[3px] border-l-success',
  warning: 'border-l-[3px] border-l-warning',
  destructive: 'border-l-[3px] border-l-destructive',
};

export function CardWrapper({ children, className, accent }: {
  children: ReactNode;
  className?: string;
  accent?: AccentColor;
}) {
  return (
    <div className={cn(
      'rounded-xl border border-border bg-card p-3.5 text-[13px] shadow-[var(--shadow-sm)] animate-card-in',
      accent && accentClasses[accent],
      className,
    )}>
      {children}
    </div>
  );
}
