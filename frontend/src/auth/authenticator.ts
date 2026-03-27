import type { AuthCredentials } from './types';

/** Strategy for obtaining credentials (popup vs mock). Only interactive acquisition is needed server-side. */
export interface UserAuthenticator {
  acquireCredentials(): Promise<AuthCredentials>;
}
