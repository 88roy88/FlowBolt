import type { Monaco, OnMount } from '@monaco-editor/react';
import { useFilesStore } from '../../stores/files';
import {
  normalizeProjectPath,
  resolveRelativeImportPath,
  findImportedModuleForSymbol,
} from './editorFilePaths';
import type { MutableRefObject, RefObject } from 'react';

type Editor = Parameters<OnMount>[0];

export function createEditorPanelMonacoOnMount(deps: {
  editorRef: MutableRefObject<Editor | null>;
  monacoRef: RefObject<Monaco | null>;
  importNavigationDisposableRef: MutableRefObject<{ dispose(): void } | null>;
  quickOpenInputRef: RefObject<HTMLInputElement | null>;
  indexedFilesRef: MutableRefObject<Set<string>>;
  openFile: (path: string, line?: number, column?: number) => Promise<void>;
  setQuickOpenVisible: (v: boolean) => void;
  setQuickOpenQuery: (q: string) => void;
  setQuickOpenSelectedIndex: (i: number | ((n: number) => number)) => void;
}): OnMount {
  return (editor: Editor) => {
    deps.editorRef.current = editor;
    const m = deps.monacoRef.current;
    if (m) {
      editor.addCommand(m.KeyMod.CtrlCmd | m.KeyCode.KeyP, () => {
        deps.setQuickOpenVisible(true);
        deps.setQuickOpenQuery('');
        deps.setQuickOpenSelectedIndex(0);
        setTimeout(() => deps.quickOpenInputRef.current?.focus(), 0);
      });
    }
    deps.importNavigationDisposableRef.current?.dispose();
    deps.importNavigationDisposableRef.current = editor.onMouseDown((event: {
      event?: globalThis.MouseEvent;
      target?: { position?: { lineNumber: number; column: number } | null };
    }) => {
      const browserEvent = event?.event;
      const isCtrlOrCmd = Boolean(browserEvent?.ctrlKey || browserEvent?.metaKey);
      if (!isCtrlOrCmd) return;

      let position = event?.target?.position ?? null;
      if (!position && browserEvent && typeof browserEvent.clientX === 'number') {
        const hit = editor.getTargetAtClientPoint(browserEvent.clientX, browserEvent.clientY);
        position = hit?.position ?? null;
      }
      if (!position) return;

      const model = editor.getModel();
      if (!model) return;

      const lineText = model.getLineContent(position.lineNumber) ?? '';
      if (!lineText.includes('import')) return;

      const word = model.getWordAtPosition(position);
      if (!word?.word) return;

      const importPath = findImportedModuleForSymbol(model.getValue(), word.word);
      if (!importPath) return;

      const currentPath = normalizeProjectPath(decodeURIComponent(model.uri.path));
      const targetPath = resolveRelativeImportPath(currentPath, importPath, deps.indexedFilesRef.current);
      if (!targetPath) return;

      browserEvent?.preventDefault?.();
      browserEvent?.stopPropagation?.();
      void deps.openFile(targetPath, 1, 1);
    });
    editor.onDidDispose(() => {
      deps.importNavigationDisposableRef.current?.dispose();
      deps.importNavigationDisposableRef.current = null;
    });
    const { pendingRevealLine: line, pendingRevealColumn: col, clearPendingReveal: clear } =
      useFilesStore.getState();
    if (line) {
      setTimeout(() => {
        const pos = { lineNumber: line, column: col ?? 1 };
        editor.setPosition(pos);
        editor.revealPositionInCenter(pos);
        editor.focus();
        clear();
      }, 50);
    }
  };
}
