import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pencil } from 'lucide-react';
import { fetchFileContent, saveFileContent } from '../../services/api';
import { useChatStore } from '../../stores/chat';
import { useErrorStore } from '../../stores/errors';
import { useFilesStore } from '../../stores/files';
import { useSessionStore } from '../../stores/session';
import { LOCK_MESSAGES, useWorkspaceLock } from '../../stores/workspaceLock';
import { withAppTitle } from '../../utils/appTitle';

const INDEX_HTML_PATH = '/index.html';
const MAX_TITLE_LENGTH = 120;

interface AppTitleProps {
  /** The preview's `<title>`, or null until the preview has reported it. */
  title: string | null;
  onChange: (title: string) => void;
}

/** The app's title; clicking it renames the app in its index.html. */
export function AppTitle({ title, onChange }: AppTitleProps) {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const projectName = useSessionStore((s) => s.currentProject?.name);
  const buildCompleted = useChatStore((s) => s.buildCompleted);
  const { lock } = useWorkspaceLock();
  const [draft, setDraft] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const canRename = title !== null && lock === null && buildCompleted;
  const label = title || projectName || '';

  const finishEditing = async () => {
    const next = draft?.trim();
    const cancelled = cancelledRef.current;
    cancelledRef.current = false;
    setDraft(null);
    if (cancelled || !next || !projectId || title === null || next === title) return;

    onChange(next);
    try {
      const html = await fetchFileContent(projectId, INDEX_HTML_PATH);
      await saveFileContent(projectId, INDEX_HTML_PATH, withAppTitle(html, next));
      useFilesStore.setState((s) => ({ saveVersion: s.saveVersion + 1 }));
      void useFilesStore.getState().refreshOpenFiles();
    } catch {
      onChange(title);
      useErrorStore.getState().pushError({ source: 'connection', message: t('preview.renameAppFailed') });
    }
  };

  if (draft !== null) {
    return (
      <input
        autoFocus
        dir="auto"
        value={draft}
        maxLength={MAX_TITLE_LENGTH}
        aria-label={t('preview.renameApp')}
        className="flex-1 min-w-0 bg-transparent text-center font-medium outline-none"
        onChange={(e) => setDraft(e.target.value)}
        onFocus={(e) => e.target.select()}
        onBlur={finishEditing}
        onKeyDown={(e) => {
          if (e.key === 'Escape') cancelledRef.current = true;
          if (e.key === 'Enter' || e.key === 'Escape') e.currentTarget.blur();
        }}
      />
    );
  }

  if (!canRename) {
    return (
      <span
        dir="auto"
        className="min-w-0 truncate font-medium"
        title={lock ? t(LOCK_MESSAGES[lock]) : label}
        data-testid="preview-app-title"
      >
        {label}
      </span>
    );
  }

  return (
    <button
      type="button"
      className="group flex items-center gap-1 min-w-0 rounded-full font-medium focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      title={t('preview.renameApp')}
      onClick={() => setDraft(title)}
      data-testid="preview-app-title"
    >
      <span dir="auto" className="truncate">{label}</span>
      <Pencil size={11} className="shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" />
    </button>
  );
}
