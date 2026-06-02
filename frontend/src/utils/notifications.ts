const STORAGE_KEY = 'notify-on-complete';
const ATTENTION_COOLDOWN_MS = 5000;

let lastAttentionAt = 0;

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

function showBrowserNotification(title: string, body: string): void {
  if (typeof window === 'undefined' || !('Notification' in window)) return;
  if (!isNotifyEnabled()) return;
  if (Notification.permission !== 'granted') return;
  if (!document.hidden) return;

  const n = new Notification(title, { body, icon: '/favicon.ico' });
  n.onclick = () => {
    window.focus();
    n.close();
  };
}

function playAttentionSound(): void {
  if (typeof window === 'undefined' || !isNotifyEnabled()) return;

  const AudioContextCtor =
    window.AudioContext ||
    (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioContextCtor) return;

  try {
    const context = new AudioContextCtor();
    const now = context.currentTime;
    const gain = context.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.16, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.55);
    gain.connect(context.destination);

    for (const [index, frequency] of [880, 1174].entries()) {
      const oscillator = context.createOscillator();
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(frequency, now + index * 0.16);
      oscillator.connect(gain);
      oscillator.start(now + index * 0.16);
      oscillator.stop(now + index * 0.16 + 0.22);
    }

    setTimeout(() => {
      void context.close();
    }, 800);
  } catch {
    // Some browsers block audio until the user interacts with the page.
  }
}

export function notifyAgentNeedsAttention(projectName?: string): void {
  const now = Date.now();
  if (now - lastAttentionAt < ATTENTION_COOLDOWN_MS) return;
  lastAttentionAt = now;

  playAttentionSound();
  showBrowserNotification(projectName ?? 'AI Builder', 'The AI agent needs your approval.');
}

export function notifyBuildComplete(projectName?: string, isError = false): void {
  const title = projectName ?? 'AI Builder';
  const body = isError ? 'An error occurred during the build.' : 'Build complete!';
  showBrowserNotification(title, body);
}
