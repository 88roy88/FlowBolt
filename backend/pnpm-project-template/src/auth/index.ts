/**
 * Authentication module — SSO via popup or iframe.
 *
 * Reads configuration from VITE_AUTH_* environment variables.
 * Provides credentialsStore for token management and authSession for sign-in flow.
 */

export { AuthGate } from './AuthGate';
export { authSession, PopupBlockedError } from './session';
export { credentialsStore } from './storage';
export { authConfig, isProviderConfigured } from './config';
export { IframeModal } from './IframeModal';
export type { AuthCredentials } from './types';
export type { SessionBootstrapResult } from './session';
