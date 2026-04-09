/**
 * Authentication module
 *
 * For local development:
 * - Set VITE_AUTH_PROVIDER_URL=http://localhost:6001/sso in .env
 * - Start mock server: cd mocks/cases-mock && pnpm start
 */

export { AuthGate } from './AuthGate';
export { authSession, PopupBlockedError } from './session';
export { credentialsStore } from './storage';
export { authConfig, isProviderConfigured } from './config';
export { IframeModal } from './IframeModal';
export type { AuthCredentials } from './types';
export type { SessionBootstrapResult } from './session';
