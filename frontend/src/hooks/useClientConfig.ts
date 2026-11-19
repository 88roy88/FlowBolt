import { queryOptions, useQuery } from '@tanstack/react-query';
import { fetchClientConfig } from '../services/api';

export const CLIENT_CONFIG_QUERY_KEY = ['client-config'];

const clientConfigQuery = queryOptions({
  queryKey: CLIENT_CONFIG_QUERY_KEY,
  queryFn: fetchClientConfig,
  staleTime: Infinity,
});

export function useClientConfig() {
  return useQuery(clientConfigQuery).data;
}

export function useFeatureFlag(key: string): boolean {
  return useClientConfig()?.features.includes(key) ?? false;
}

export function useFeatureFlagState(key: string): boolean | 'loading' {
  const { data, isPending } = useQuery(clientConfigQuery);
  if (isPending) return 'loading';
  return data?.features.includes(key) ?? false;
}
