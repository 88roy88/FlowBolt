import { useEffect, useState } from 'react';
import { fetchClientConfig, type ClientConfig } from '../services/api';

let cached: ClientConfig | null = null;
let pending: Promise<ClientConfig | null> | null = null;

function load(): Promise<ClientConfig | null> {
  pending ??= fetchClientConfig()
    .then((config) => (cached = config))
    .catch((err) => {
      console.error('Failed to load client config:', err);
      pending = null; // retry on next mount
      return null;
    });
  return pending;
}

/** Backend-provided client settings, or null until loaded. */
export function useClientConfig(): ClientConfig | null {
  const [config, setConfig] = useState(cached);
  useEffect(() => {
    if (cached !== null) return;
    let alive = true;
    void load().then((value) => alive && setConfig(value));
    return () => {
      alive = false;
    };
  }, []);
  return config;
}

export function isOverLimit(length: number, max: number | null): boolean {
  return max !== null && length > max;
}
