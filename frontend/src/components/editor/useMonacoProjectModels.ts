import { useCallback, useEffect, useRef } from 'react';
import type { Monaco } from '@monaco-editor/react';
import type { FileEntry } from '../../types';
import { fetchFileContent } from '../../services/api';
import {
  toMonacoUri,
  normalizeProjectPath,
  flattenFileTreeEntries,
} from './editorFilePaths';
import { getEditorLanguageForPath } from './editorLanguage';
import { installMonacoProjectTypes } from './monacoProjectSetup';
import { MONACO_REACT_VITE_DTS_URI, MONACO_REACT_VITE_JS_DTS_URI } from './monacoAmbientTypes';

export function useMonacoProjectModels(
  projectId: string | null,
  fileTree: FileEntry[],
  openFiles: Map<string, string>
) {
  const monacoRef = useRef<Monaco | null>(null);
  const hydratedModelsRef = useRef<Set<string>>(new Set());
  const indexedFilesRef = useRef<Set<string>>(new Set());
  const openFilesRef = useRef(openFiles);

  useEffect(() => {
    openFilesRef.current = openFiles;
  }, [openFiles]);

  useEffect(() => {
    const m = monacoRef.current;
    if (!m) return;

    hydratedModelsRef.current.clear();
    indexedFilesRef.current.clear();

    for (const model of m.editor.getModels()) {
      const uri = model.uri.toString();

      if (uri === MONACO_REACT_VITE_DTS_URI || uri === MONACO_REACT_VITE_JS_DTS_URI) {
        continue;
      }

      model.dispose();
    }
  }, [projectId]);

  useEffect(() => {
    const m = monacoRef.current;
    if (!m || !projectId || fileTree.length === 0) return;

    let cancelled = false;

    const files = flattenFileTreeEntries(fileTree)
      .map((p: string) => normalizeProjectPath(p))
      .filter((p: string) => /\.(ts|tsx|js|jsx|mjs|cjs|json|css|scss|sass|less)$/.test(p));

    for (const path of files) {
      const uri = m.Uri.parse(toMonacoUri(path));
      if (m.editor.getModel(uri)) continue;
      m.editor.createModel('', getEditorLanguageForPath(path), uri);
    }

    const hydrateModels = async () => {
      const tasks = files.map(async (path: string) => {
        const uri = toMonacoUri(path);
        if (hydratedModelsRef.current.has(uri) || openFilesRef.current.has(path)) return;

        try {
          const content = await fetchFileContent(projectId, path);
          if (cancelled) return;

          const model = m.editor.getModel(m.Uri.parse(uri));
          if (!model) return;
          if (model.getValue() !== content) {
            model.setValue(content);
          }
          hydratedModelsRef.current.add(uri);
        } catch {
          // ignore
        }
      });

      await Promise.allSettled(tasks);
    };

    void hydrateModels();

    return () => {
      cancelled = true;
    };
  }, [projectId, fileTree]);

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
