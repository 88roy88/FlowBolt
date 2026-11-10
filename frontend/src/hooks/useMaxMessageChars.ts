import { useEffect, useState } from 'react';
import { fetchChatLimits } from '../services/api';

let cached: number | null = null;
let pending: Promise<number | null> | null = null;

function load(): Promise<number | null> {
  pending ??= fetchChatLimits()
    .then((limits) => (cached = limits.max_message_chars))
    .catch((err) => {
      console.error('Failed to load chat limits:', err);
      pending = null; // retry on next mount; the backend still enforces the limit
      return null;
    });
  return pending;
}

/** The backend's max chat message length, or null until it has loaded. */
export function useMaxMessageChars(): number | null {
  const [max, setMax] = useState(cached);
  useEffect(() => {
    if (cached !== null) return;
    let alive = true;
    void load().then((value) => alive && setMax(value));
    return () => {
      alive = false;
    };
  }, []);
  return max;
}

export function isOverLimit(length: number, max: number | null): boolean {
  return max !== null && length > max;
}
