import { AlertTriangle, X, Wrench, RefreshCw } from 'lucide-react';
import { useErrorStore, type AppError } from '../../stores/errors';
import { useSessionStore } from '../../stores/session';
import { useChatStore } from '../../stores/chat';
import { useFilesStore } from '../../stores/files';
import { Button } from '../ui/button';

export { useErrorCapture } from '../../hooks/useErrorCapture';

function normalizeFilePath(filePath: string): string {
  const srcIdx = filePath.indexOf('/src/');
  if (srcIdx !== -1) return filePath.slice(srcIdx);
  if (!filePath.startsWith('/src/')) {
    if (!filePath.startsWith('/')) filePath = '/' + filePath;
    return '/src' + filePath;
  }
  return filePath;
}

function SingleErrorToast({ error }: { error: AppError }) {
  const dismissError = useErrorStore((s) => s.dismissError);
  const sendFixError = useChatStore((s) => s.sendFixError);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const openFile = useFilesStore((s) => s.openFile);
  const loadProjects = useSessionStore((s) => s.loadProjects);

  const handleFix = () => {
    sendFixError(error.message, error.file, error.line, error.stack);
    dismissError(error.id);
  };

  const handleRetry = async () => {
    dismissError(error.id);
    try {
      await loadProjects();
    } catch (err) {
      console.error('Retry failed:', err);
    }
  };

  return (
    <div className="flex items-start gap-2.5 p-3 bg-card border border-destructive rounded-lg max-w-[420px] shadow-[var(--shadow-lg)]">
      <AlertTriangle size={18} className="text-destructive shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-semibold text-destructive uppercase tracking-wider mb-1">
          {error.source === 'build' ? 'Build Error' : error.source === 'runtime' ? 'Runtime Error' : 'Connection Error'}
        </div>
        <div className="text-[13px] leading-snug break-words">
          {error.message.length > 150 ? error.message.slice(0, 150) + '...' : error.message}
        </div>
        {error.file && (
          <button
            onClick={() => openFile(normalizeFilePath(error.file!), error.line, error.column)}
            className="block text-[11px] text-primary underline mt-1.5 text-left cursor-pointer"
            title="Open in editor"
          >
            {error.file}{error.line ? `:${error.line}` : ''}
          </button>
        )}
        {error.source === 'connection' ? (
          <Button variant="outline" size="sm" onClick={handleRetry} className="mt-2.5 ml-auto">
            <RefreshCw size={12} />
            Retry
          </Button>
        ) : (
          <Button variant="outline" size="sm" onClick={handleFix} disabled={isStreaming} className="mt-2.5 ml-auto">
            <Wrench size={12} />
            Fix with AI
          </Button>
        )}
      </div>
      <button onClick={() => dismissError(error.id)} className="p-0.5 text-muted-foreground shrink-0" title="Dismiss">
        <X size={14} />
      </button>
    </div>
  );
}

export function ErrorToast() {
  const errors = useErrorStore((s) => s.errors);
  if (errors.length === 0) return null;

  return (
    <div className="fixed top-3 right-3 z-[9999] flex flex-col gap-2">
      {errors.map((error) => (
        <SingleErrorToast key={error.id} error={error} />
      ))}
    </div>
  );
}
