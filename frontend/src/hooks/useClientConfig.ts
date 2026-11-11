import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig, type ClientConfig } from '../services/api';

/** Backend-provided client settings, or null until loaded. */
export function useClientConfig(): ClientConfig | null {
  const { data } = useQuery({ queryKey: ['client-config'], queryFn: fetchClientConfig, staleTime: Infinity });
  return data ?? null;
}

export function isOverLimit(length: number, max: number | null): boolean {
  return max !== null && length > max;
}
