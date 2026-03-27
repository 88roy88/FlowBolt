import { credentialsStore } from '../auth/credentialsStore';

/** Value for the `Authorization` header when calling data-source proxies (and Flapi upstream). */
export function readDataSourceAuthorization(): string | undefined {
  return credentialsStore.getValidAccessToken();
}
