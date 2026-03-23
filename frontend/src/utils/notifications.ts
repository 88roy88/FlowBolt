const STORAGE_KEY = 'notify-on-complete';

export function isNotifyEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(STORAGE_KEY) !== 'false';
}

export function setNotifyEnabled(enabled: boolean): void {
  localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false');
}

export async function requestPermissionIfNeeded(): Promise<void> {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (Notification.permission === 'default') {
    await Notification.requestPermission();
  }
}

export function notifyBuildComplete(projectName?: string, isError = false): void {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (!isNotifyEnabled()) return;
  if (Notification.permission !== 'granted') return;
  if (!document.hidden) return;

  const title = projectName ?? 'AI Builder';
  const body = isError ? 'An error occurred during the build.' : 'Build complete!';

  const n = new Notification(title, { body, icon: '/favicon.ico' });
  n.onclick = () => {
    window.focus();
    n.close();
  };
}
