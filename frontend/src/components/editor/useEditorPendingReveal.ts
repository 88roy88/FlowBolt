import { useEffect, type MutableRefObject } from 'react';
import type { OnMount } from '@monaco-editor/react';

export function useEditorPendingReveal(
  editorRef: MutableRefObject<Parameters<OnMount>[0] | null>,
  pendingRevealLine: number | null,
  pendingRevealColumn: number | null,
  revealVersion: number,
  activeFilePath: string | null,
  clearPendingReveal: () => void
) {
  useEffect(() => {
    if (!pendingRevealLine || !editorRef.current) return;
    const line = pendingRevealLine;
    const col = pendingRevealColumn ?? 1;
    const timer = setTimeout(() => {
      const editor = editorRef.current;
      if (!editor) return;
      const pos = { lineNumber: line, column: col };
      editor.setPosition(pos);
      editor.revealPositionInCenter(pos);
      editor.focus();
    }, 100);
    clearPendingReveal();
    return () => clearTimeout(timer);
  }, [pendingRevealLine, pendingRevealColumn, revealVersion, activeFilePath, clearPendingReveal, editorRef]);
}
