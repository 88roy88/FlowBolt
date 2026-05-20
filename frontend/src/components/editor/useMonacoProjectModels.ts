import { useCallback, useEffect, useRef } from 'react';
import type { Monaco, OnMount } from '@monaco-editor/react';
import type { FileEntry } from '../../types';
import { useFilesStore } from '../../stores/files';
import {
  toMonacoUri,
  normalizeProjectPath,
  flattenFileTreeEntries,
  getEditorLanguageForPath,
} from './editorFilePaths';
import { installMonacoProjectTypes } from './monacoProjectSetup';
import { MONACO_REACT_VITE_DTS_URI, MONACO_REACT_VITE_JS_DTS_URI } from './monacoAmbientTypes';
import type { MutableRefObject } from 'react';

type Editor = Parameters<OnMount>[0];

function syncModelContent(m: Monaco, storePath: string, content: string) {
  const uri = m.Uri.parse(toMonacoUri(normalizeProjectPath(storePath)));
  const model = m.editor.getModel(uri);
  if (model && model.getValue() !== content) {
    model.setValue(content);
  }
}

export function useMonacoProjectModels(
  projectId: string | null,
  fileTree: FileEntry[],
  openFile: (path: string, line?: number, column?: number) => Promise<void>,
  onRequestQuickOpen: () => void,
): {
  handleBeforeMount: (m: Monaco) => void;
  handleOnMount: OnMount;
  monacoRef: MutableRefObject<Monaco | null>;
  editorRef: MutableRefObject<Editor | null>;
} {
  const monacoRef = useRef<Monaco | null>(null);
  const editorRef = useRef<Editor | null>(null);
  const indexedFilesRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const m = monacoRef.current;
    if (!m) return;

    const modelsToDispose = m.editor.getModels().filter((model: { uri: { toString(): string } }) => {
      const uri = model.uri.toString();
      return uri !== MONACO_REACT_VITE_DTS_URI && uri !== MONACO_REACT_VITE_JS_DTS_URI;
    });

    for (const model of modelsToDispose) {
      try {
        if (!model.isDisposed()) {
          model.dispose();
        }
      } catch (error) {
        console.error('Failed to dispose Monaco model:', model.uri.toString(), error);
        try {
          const uri = model.uri;
          const tempModel = m.editor.createModel('', 'plaintext', uri);
          tempModel.dispose();
          model.dispose();
        } catch {
          console.error('Could not recover from failed model disposal:', model.uri.toString());
        }
      }
    }
  }, [projectId]);

  useEffect(() => {
    const allPaths = flattenFileTreeEntries(fileTree).map((p: string) => normalizeProjectPath(p));
    indexedFilesRef.current = new Set(allPaths);

    const m = monacoRef.current;
    if (!m || !projectId || fileTree.length === 0) return;

    const modelFiles = allPaths.filter((p: string) =>
      /\.(ts|tsx|js|jsx|mjs|cjs|json|css|scss|sass|less)$/.test(p)
    );
    for (const path of modelFiles) {
      const uri = m.Uri.parse(toMonacoUri(path));
      if (m.editor.getModel(uri)) continue;
      m.editor.createModel('', getEditorLanguageForPath(path), uri);
    }

    for (const [storePath, content] of useFilesStore.getState().openFiles) {
      syncModelContent(m, storePath, content);
    }
  }, [projectId, fileTree]);

  useEffect(() => {
    return useFilesStore.subscribe((state, prevState) => {
      const m = monacoRef.current;
      if (!m || state.openFiles === prevState.openFiles) return;
      for (const [storePath, content] of state.openFiles) {
        if (prevState.openFiles.get(storePath) === content) continue;
        syncModelContent(m, storePath, content);
      }
    });
  }, []);

  const handleBeforeMount = useCallback((m: Monaco) => {
    monacoRef.current = m;
    installMonacoProjectTypes(m, () => indexedFilesRef.current, openFile);
  }, [openFile]);

  const handleOnMount: OnMount = useCallback((editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyP, onRequestQuickOpen);

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
  }, [onRequestQuickOpen]);

  return { handleBeforeMount, handleOnMount, monacoRef, editorRef };
}
