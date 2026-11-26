import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export function useClientConfigQuery() {
  return useQuery({ queryKey: ['client-config'], queryFn: fetchClientConfig, staleTime: Infinity });
}

export function useClientConfig() {
  return useClientConfigQuery().data;
}
