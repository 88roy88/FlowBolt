import { useCallback, useEffect, useRef } from 'react';
import type { Monaco } from '@monaco-editor/react';
import type { FileEntry } from '../../types';
import { useFilesStore } from '../../stores/files';
import {
  toMonacoUri,
  normalizeProjectPath,
  flattenFileTreeEntries,
} from './editorFilePaths';
import { getEditorLanguageForPath } from './editorLanguage';
import { installMonacoProjectTypes } from './monacoProjectSetup';
import { MONACO_REACT_VITE_DTS_URI, MONACO_REACT_VITE_JS_DTS_URI } from './monacoAmbientTypes';

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
) {
  const monacoRef = useRef<Monaco | null>(null);
  const indexedFilesRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const m = monacoRef.current;
    if (!m) return;

    indexedFilesRef.current.clear();

    // Dispose models for previous project
    const modelsToDispose = m.editor.getModels().filter((model: { uri: { toString(): string } }) => {
      const uri = model.uri.toString();
      return uri !== MONACO_REACT_VITE_DTS_URI && uri !== MONACO_REACT_VITE_JS_DTS_URI;
    });

    for (const model of modelsToDispose) {
      try {
        // Check if model is still valid before disposing
        if (!model.isDisposed()) {
          model.dispose();
        }
      } catch (error) {
        console.error('Failed to dispose Monaco model:', model.uri.toString(), error);
        // Force removal from editor's model collection if disposal fails
        try {
          const uri = model.uri;
          // Create a new model with same URI to replace the broken one, then dispose both
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
    const m = monacoRef.current;
    if (!m || !projectId || fileTree.length === 0) return;

    const files = flattenFileTreeEntries(fileTree)
      .map((p: string) => normalizeProjectPath(p))
      .filter((p: string) => /\.(ts|tsx|js|jsx|mjs|cjs|json|css|scss|sass|less)$/.test(p));

    for (const path of files) {
      const uri = m.Uri.parse(toMonacoUri(path));
      if (m.editor.getModel(uri)) continue;
      m.editor.createModel('', getEditorLanguageForPath(path), uri);
    }

    // Sync files already open in the store (e.g. tabs restored from localStorage
    // before this effect ran).
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

  useEffect(() => {
    indexedFilesRef.current = new Set(
      flattenFileTreeEntries(fileTree).map((path: string) => normalizeProjectPath(path))
    );
  }, [fileTree]);

  const handleBeforeMount = useCallback((m: Monaco) => {
    monacoRef.current = m;
    installMonacoProjectTypes(m, () => indexedFilesRef.current);
  }, []);

  return { monacoRef, indexedFilesRef, handleBeforeMount };
}
