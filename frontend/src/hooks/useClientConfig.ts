import { useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export const CLIENT_CONFIG_QUERY_KEY = ['client-config'];

function useClientConfigQuery() {
  return useQuery({ queryKey: CLIENT_CONFIG_QUERY_KEY, queryFn: fetchClientConfig, staleTime: Infinity });
}

export function useClientConfig() {
  return useClientConfigQuery().data;
}

export function useFeatureFlag(key: string): boolean {
  return useClientConfig()?.features.includes(key) ?? false;
}

// For flags that must be known before first render. `ready` is also true when the fetch failed (flag off).
export function useFeatureFlagState(key: string): { enabled: boolean; ready: boolean } {
  const { data, isPending } = useClientConfigQuery();
  return { enabled: data?.features.includes(key) ?? false, ready: !isPending };
}
