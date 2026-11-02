import { logger } from '../services/logger';

type AbortOutcome = 'aborted' | 'too_late';

let requestedAt: number | null = null;

export function markAbortRequested() {
  requestedAt = performance.now();
}

export function forgetAbortRequest() {
  requestedAt = null;
}

/** Logs how a Stop ended: the run was aborted, or the turn finished before the abort reached it. */
export function settleAbort(outcome: AbortOutcome) {
  if (requestedAt === null) return;
  logger.info('response_aborted', { outcome, elapsed_ms: Math.round(performance.now() - requestedAt) });
  requestedAt = null;
}
