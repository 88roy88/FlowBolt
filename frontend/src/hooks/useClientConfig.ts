import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig, type ClientConfig } from '../services/api';

export function useClientConfig(): ClientConfig | null {
  const { data } = useQuery({ queryKey: ['client-config'], queryFn: fetchClientConfig, staleTime: Infinity });
  return data ?? null;
}
