import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TFunction } from 'i18next';
import { formatClock, formatDayDivider, sameDay } from '../formatTime';

const t = ((_key: string, fallback: string) => fallback) as unknown as TFunction;

const at = (h: number, m: number, dayOffset = 0) => {
  const d = new Date(2026, 6, 20, h, m, 0, 0);
  d.setDate(d.getDate() + dayOffset);
  return d.getTime();
};

beforeEach(() => vi.setSystemTime(new Date(2026, 6, 20, 12, 0, 0)));
afterEach(() => vi.useRealTimers());

describe('formatClock', () => {
  it('formats 24-hour clock time', () => {
    expect(formatClock(at(14, 32), 'en')).toBe('14:32');
    expect(formatClock(at(9, 5), 'he')).toBe('09:05');
  });
});

describe('sameDay', () => {
  it('is true within a day and false across midnight', () => {
    expect(sameDay(at(1, 0), at(23, 59))).toBe(true);
    expect(sameDay(at(23, 59), at(0, 1, 1))).toBe(false);
  });
});

describe('formatDayDivider', () => {
  it('labels today and yesterday', () => {
    expect(formatDayDivider(at(10, 0), 'en', t)).toBe('Today');
    expect(formatDayDivider(at(10, 0, -1), 'en', t)).toBe('Yesterday');
  });

  it('falls back to a full date for older days', () => {
    expect(formatDayDivider(at(10, 0, -5), 'en', t)).not.toMatch(/Today|Yesterday/);
  });
});
