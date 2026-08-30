import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, RefreshCw, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '../ui/button';

type Variant = 'screen' | 'panel';

function ErrorFallback({ error, variant, onReset }: { error: Error; variant: Variant; onReset: () => void }) {
  const { t } = useTranslation();
  const isScreen = variant === 'screen';

  return (
    <div className={cn('flex flex-col items-center justify-center h-full w-full gap-4 p-6 text-center', isScreen && 'gap-6 px-8')}>
      <div className={cn('w-full max-w-md px-5 py-4 bg-surface rounded-xl border-2 border-destructive/50', isScreen && 'shadow-[0_0_20px_color-mix(in_srgb,var(--destructive)_10%,transparent)]')}>
        <AlertTriangle size={isScreen ? 22 : 18} className="text-destructive mx-auto mb-2" />
        <p className={cn('text-destructive font-semibold mb-1.5', !isScreen && 'text-sm')}>
          {t('errors.somethingWentWrong', 'Something went wrong')}
        </p>
        <p className={cn('text-sm text-muted-foreground break-words', !isScreen && 'text-xs')}>{error.message}</p>
      </div>

      <div className="flex gap-2">
        <Button variant="outline" size={isScreen ? 'default' : 'sm'} onClick={onReset}>
          <RotateCcw size={12} />
          {t('errors.retry', 'Retry')}
        </Button>
        <Button variant="outline" size={isScreen ? 'default' : 'sm'} onClick={() => window.location.reload()}>
          <RefreshCw size={12} />
          {t('errors.reloadPage', 'Reload page')}
        </Button>
      </div>

      {import.meta.env.DEV && error.stack && (
        <details className="w-full max-w-2xl text-start">
          <summary className="text-xs text-muted-foreground cursor-pointer">{t('errors.errorDetails', 'Error details')}</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded-lg border border-border bg-card p-3 text-[11px] leading-snug whitespace-pre-wrap break-words">
            {error.stack}
          </pre>
        </details>
      )}
    </div>
  );
}

export class ErrorBoundary extends Component<
  { children: ReactNode; variant?: Variant },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <ErrorFallback
        error={error}
        variant={this.props.variant ?? 'panel'}
        onReset={() => this.setState({ error: null })}
      />
    );
  }
}
