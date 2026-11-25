import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export const CLIENT_CONFIG_QUERY_KEY = ['client-config'];

export function useClientConfig() {
  return useQuery({ queryKey: CLIENT_CONFIG_QUERY_KEY, queryFn: fetchClientConfig, staleTime: Infinity }).data;
}

export function useFeatureFlag(key: string): boolean {
  return useClientConfig()?.features.includes(key) ?? false;
}
