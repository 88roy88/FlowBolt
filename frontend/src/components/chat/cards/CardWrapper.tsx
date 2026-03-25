import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

type AccentColor = 'primary' | 'success' | 'warning' | 'destructive';

const accentClasses: Record<AccentColor, string> = {
  primary: 'border-s-[3px] border-s-primary',
  success: 'border-s-[3px] border-s-success',
  warning: 'border-s-[3px] border-s-warning',
  destructive: 'border-s-[3px] border-s-destructive',
};

export function CardWrapper({ children, className, accent }: {
  children: ReactNode;
  className?: string;
  accent?: AccentColor;
}) {
  return (
    <div className={cn(
      'max-w-[85%] rounded-xl border border-border bg-card p-3.5 text-[13px] shadow-[var(--shadow-sm)] animate-card-in',
      accent && accentClasses[accent],
      className,
    )}>
      {children}
    </div>
  );
}
