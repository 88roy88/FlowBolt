import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export const CLIENT_CONFIG_QUERY_KEY = ['client-config'];

// Polled, background tabs included, so open tabs notice the disable_workspaces kill switch.
const REFETCH_MS = 30_000;

export function useClientConfigQuery() {
  return useQuery({
    queryKey: CLIENT_CONFIG_QUERY_KEY,
    queryFn: fetchClientConfig,
    staleTime: Infinity,
    refetchInterval: REFETCH_MS,
    refetchIntervalInBackground: true,
  });
}

export function useClientConfig() {
  return useClientConfigQuery().data;
}

export function useFeatureFlag(key: string): boolean {
  return useClientConfig()?.features.includes(key) ?? false;
}
