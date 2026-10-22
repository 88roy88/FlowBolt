export function getProjectHasMessages(projectId: string): boolean | null {
  try {
    const cached = localStorage.getItem(`project-has-messages:${projectId}`);
    if (cached === 'true') return true;
    if (cached === 'false') return false;
    return null;
  } catch {
    return null;
  }
}

export function setProjectHasMessages(projectId: string, hasMessages: boolean) {
  try {
    localStorage.setItem(`project-has-messages:${projectId}`, hasMessages ? 'true' : 'false');
  } catch {}
}
