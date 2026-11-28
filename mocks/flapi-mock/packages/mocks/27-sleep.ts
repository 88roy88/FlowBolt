import { MockPackage, buildMetadata, quickParamsQuery } from '../package-base.js';

const DEFAULT_SECONDS = 5;
const MAX_SECONDS = 600;

const data = { Sleep: [{ slept_seconds: 2.5, started_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:00:02Z' }] };

export default new MockPackage({
  metadata: buildMetadata(27, 'Sleep', data, {
    description: `Waits before returning. Waits ${DEFAULT_SECONDS} seconds unless "seconds" is given.`,
  }),
  quickParams: quickParamsQuery('sleep-query-1', [
    {
      name: 'seconds',
      displayName: 'Seconds',
      type: 'Double',
      required: false,
      singleValue: true,
      description: `How long to wait, in seconds (default ${DEFAULT_SECONDS}, at most ${MAX_SECONDS}).`,
    },
  ]),
  async getResults(quickParams) {
    const requested = Number(quickParams.seconds ?? DEFAULT_SECONDS);
    const seconds = Number.isFinite(requested) ? Math.min(Math.max(requested, 0), MAX_SECONDS) : DEFAULT_SECONDS;
    const startedAt = new Date().toISOString();
    await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
    return { Sleep: [{ slept_seconds: seconds, started_at: startedAt, finished_at: new Date().toISOString() }] };
  },
});
