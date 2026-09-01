import { format, isSameDay, isToday, isYesterday } from 'date-fns';
import { enUS, he } from 'date-fns/locale';
import type { Locale } from 'date-fns';
import type { TFunction } from 'i18next';

function resolveLocale(lang: string): Locale {
  return lang.startsWith('he') ? he : enUS;
}

export function formatClock(ts: number, lang: string): string {
  return format(ts, 'HH:mm', { locale: resolveLocale(lang) });
}

export function sameDay(a: number, b: number): boolean {
  return isSameDay(a, b);
}

export function formatDayDivider(ts: number, lang: string, t: TFunction): string {
  if (isToday(ts)) return t('chat.today', 'Today');
  if (isYesterday(ts)) return t('chat.yesterday', 'Yesterday');
  return format(ts, 'PPP', { locale: resolveLocale(lang) });
}
