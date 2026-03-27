import type { AuthRuntimeConfig } from './config';
import type { AuthCredentials } from './types';

/**
 * Dev / E2E authenticator — no popup; writes mock credentials synchronously.
 */
export class MockAuthenticator {
  constructor(private readonly config: AuthRuntimeConfig) {}

  acquireCredentials(): Promise<AuthCredentials> {
    const creds: AuthCredentials = {
      auth_token: this.config.mockAuthToken,
      userId: this.config.mockUserId,
      userName: this.config.mockUserName,
    };
    return Promise.resolve(creds);
  }
}
