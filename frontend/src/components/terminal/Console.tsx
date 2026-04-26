import { useEffect, useRef, useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConsoleStore, type ConsoleLevel } from '../../stores/console';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { fetchFileContent } from '../../services/api';
import { Trash2 } from 'lucide-react';

const LEVEL_COLORS: Record<ConsoleLevel, string> = {
  log: 'text-foreground',
  info: 'text-primary',
  warn: 'text-warning',
  error: 'text-destructive',
};

const LEVEL_BG: Record<ConsoleLevel, string> = {
  log: '',
  info: '',
  warn: 'bg-warning/10',
  error: 'bg-destructive/10',
};

function resolveSourceLine(file: string, args: string[]): Promise<number | undefined> {
  const projectId = useSessionStore.getState().projectId;
  if (!projectId) return Promise.resolve(undefined);
  return fetchFileContent(projectId, file)
    .then((content) => {
      const lines = content.split('\n');
      const searchStr = args[0];
      if (!searchStr) return undefined;
      const idx = lines.findIndex((l) => l.includes(searchStr));
      return idx >= 0 ? idx + 1 : undefined;
    })
    .catch(() => undefined);
}

function FileLink({ file, args }: { file: string; args: string[] }) {
  const openFile = useFilesStore((s) => s.openFile);
  const shortName = file.replace(/^src\//, '');
  const [line, setLine] = useState<number | undefined>();

  useEffect(() => {
    resolveSourceLine(file, args).then(setLine);
  }, [file, args]);

  const handleClick = useCallback(() => {
    openFile(file, line);
  }, [file, line, openFile]);

  return (
    <button
      onClick={handleClick}
      className="text-muted-foreground hover:text-primary hover:underline transition-colors"
      title={`${file}${line ? ':' + line : ''}`}
    >
      {shortName}{line ? ':' + line : ''}
    </button>
  );
}

export function Console() {
  const { t } = useTranslation();
  const entries = useConsoleStore((s) => s.entries);
  const clear = useConsoleStore((s) => s.clear);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  return (
    <div className="flex flex-col h-full bg-background">
      <div className="flex items-center justify-between px-3 py-1 border-b border-border shrink-0">
        <span className="text-[11px] text-muted-foreground">
          {entries.length} {entries.length === 1 ? t('terminal.entry') : t('terminal.entries')}
        </span>
        <button
          onClick={clear}
          className="p-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors"
          title={t('terminal.clearConsole')}
        >
          <Trash2 size={12} />
        </button>
      </div>
      <div className="flex-1 overflow-auto font-mono text-[12px] leading-[1.6]">
        {entries.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-[12px]">
            {t('terminal.noConsoleOutput')}
          </div>
        ) : (
          entries.map((entry) => (
            <div
              key={entry.id}
              className={`flex gap-2 px-3 py-0.5 border-b border-border/30 ${LEVEL_BG[entry.level]}`}
            >
              <span className="text-muted-foreground shrink-0 w-[52px]">
                {new Date(entry.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
              <span className={`shrink-0 w-[38px] ${LEVEL_COLORS[entry.level]}`}>
                {entry.level === 'log' ? ' log' : entry.level}
              </span>
              <span className={`flex-1 ${LEVEL_COLORS[entry.level]}`}>
                {entry.args.join(' ')}
              </span>
              {entry.file && (
                <span className="shrink-0 text-[11px]">
                  <FileLink file={entry.file} args={entry.args} />
                </span>
              )}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
