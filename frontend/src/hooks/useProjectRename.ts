import { useState } from 'react';
import { useSessionStore } from '../stores/session';
import type { Project } from '../types';

/** Inline rename state for a project row. */
export function useProjectRename() {
  const renameProject = useSessionStore((s) => s.renameProject);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');

  return {
    renamingId,
    renameValue,
    setRenameValue,
    start: (project: Project) => {
      setRenamingId(project.id);
      setRenameValue(project.name);
    },
    cancel: () => setRenamingId(null),
    submit: async () => {
      if (!renamingId || !renameValue.trim()) {
        setRenamingId(null);
        return;
      }
      await renameProject(renamingId, renameValue.trim());
      setRenamingId(null);
    },
  };
}
