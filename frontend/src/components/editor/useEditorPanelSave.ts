import { useEffect, useRef, useCallback, useState } from 'react';
import { useFilesStore } from '../../stores/files';

export function useEditorPanelSave(
  activeFilePath: string | null,
  readOnly: boolean
) {
  const { updateFileContent, saveFile } = useFilesStore();
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const doSave = useCallback(
    (path: string) => {
      setSaveStatus('saving');
      saveFile(path)
        .then(() => {
          setSaveStatus('saved');
          setTimeout(() => setSaveStatus('idle'), 1500);
        })
        .catch(() => setSaveStatus('idle'));
    },
    [saveFile]
  );

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (readOnly) return;
      if (!activeFilePath || value === undefined) return;
      updateFileContent(activeFilePath, value);

      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      saveTimerRef.current = setTimeout(() => {
        doSave(activeFilePath);
      }, 1000);
    },
    [activeFilePath, updateFileContent, doSave, readOnly]
  );

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    function onKeyDown(e: globalThis.KeyboardEvent) {
      if (readOnly) return;
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        const path = useFilesStore.getState().activeFilePath;
        if (path) {
          if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
          doSave(path);
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [doSave, readOnly]);

  return { saveStatus, handleEditorChange };
}
