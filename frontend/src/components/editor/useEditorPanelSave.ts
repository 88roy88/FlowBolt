import { useEffect, useCallback, useState } from 'react';
import { useFilesStore } from '../../stores/files';
import { workspaceLocked } from '../../stores/workspaceLock';
import { useDebouncedCallback } from '../../hooks/useDebounce';

export function useEditorPanelSave(
  activeFilePath: string | null,
  updateFileContent: (path: string, content: string) => void,
  saveFile: (path: string) => Promise<void>,
  readOnly: boolean
) {
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle');

  const doSave = useCallback(
    (path: string) => {
      if (workspaceLocked()) return;
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

  const debouncedSave = useDebouncedCallback(doSave, 1000);

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (readOnly) return;
      if (!activeFilePath || value === undefined) return;
      // Monaco echoes store-driven setValue() back as a change — that is a refresh, not an edit.
      if (value === useFilesStore.getState().openFiles.get(activeFilePath)) return;
      updateFileContent(activeFilePath, value);
      debouncedSave(activeFilePath);
    },
    [activeFilePath, updateFileContent, debouncedSave, readOnly]
  );

  useEffect(() => {
    function onKeyDown(e: globalThis.KeyboardEvent) {
      if (readOnly) return;
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        const path = useFilesStore.getState().activeFilePath;
        if (path) {
          debouncedSave.cancel();
          doSave(path);
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [debouncedSave, doSave, readOnly]);

  return { saveStatus, handleEditorChange, doSave };
}
