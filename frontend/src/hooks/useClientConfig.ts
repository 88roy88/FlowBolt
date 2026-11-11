import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export function useClientConfig() {
  return useQuery({ queryKey: ['client-config'], queryFn: fetchClientConfig, staleTime: Infinity }).data;
}
