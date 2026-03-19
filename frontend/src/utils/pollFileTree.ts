import { useFilesStore } from '../stores/files';

export function pollFileTree(maxAttempts = 15, intervalMs = 2000) {
  let attempts = 0;
  const interval = setInterval(async () => {
    attempts++;
    await useFilesStore.getState().loadFileTree();
    const tree = useFilesStore.getState().fileTree;
    if (tree.length > 0 || attempts >= maxAttempts) {
      clearInterval(interval);
    }
  }, intervalMs);
}
