/**
 * Data source authorization helper.
 *
 * Reads the auth token from the new auth storage system.
 * This token is sent to the backend which forwards it to FLAPI.
 */

import { credentialsStore } from '../auth';

export function readDataSourceAuthorization(): string | undefined {
  return credentialsStore.getValidToken();
}
