import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function CardWrapper({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-3.5 text-[13px] shadow-[var(--shadow-sm)] animate-card-in', className)}>
      {children}
    </div>
  );
}
