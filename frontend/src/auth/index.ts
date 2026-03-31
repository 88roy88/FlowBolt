/**
 * Authentication module - production only, no mock code.
 *
 * For local development:
 * - Set VITE_AUTH_PROVIDER_URL=http://localhost:6000/sso in .env
 * - Start mock server: cd mocks/cases-mock && pnpm start
 */

export { authSession, PopupBlockedError } from './session';
export { credentialsStore } from './storage';
export { authConfig, isProviderConfigured } from './config';
export type { AuthCredentials } from './types';
export type { SessionBootstrapResult } from './session';
