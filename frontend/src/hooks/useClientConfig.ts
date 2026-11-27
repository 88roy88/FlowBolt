import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export const CLIENT_CONFIG_QUERY_KEY = ['client-config'];

export function useClientConfigQuery() {
  return useQuery({ queryKey: CLIENT_CONFIG_QUERY_KEY, queryFn: fetchClientConfig, staleTime: Infinity });
}

export function useClientConfig() {
  return useClientConfigQuery().data;
}

export function useFeatureFlag(key: string): boolean {
  return useClientConfig()?.features.includes(key) ?? false;
}
