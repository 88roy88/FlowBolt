export function getProjectHasMessages(projectId: string): boolean | null {
  try {
    const v = localStorage.getItem(`project-has-messages:${projectId}`);
    if (v === 'true') return true;
    if (v === 'false') return false;
    return null; // No cache
  } catch {
    return null;
  }
}

export function setProjectHasMessages(projectId: string, hasMessages: boolean) {
  try {
    localStorage.setItem(`project-has-messages:${projectId}`, hasMessages ? 'true' : 'false');
  } catch {}
}
