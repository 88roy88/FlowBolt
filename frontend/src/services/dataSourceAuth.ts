import { credentialsStore } from '../auth';

export function readDataSourceAuthorization(): string | undefined {
  return credentialsStore.getValidToken();
}
