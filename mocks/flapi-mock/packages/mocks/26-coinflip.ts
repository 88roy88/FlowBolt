import { MockPackage, MockPackageError, buildMetadata } from '../package-base.js';

// Fails half the time, for testing how apps handle data source errors.
const data = { Coin: { side: 'Heads', flipped_at: '2026-01-01T00:00:00Z' } };

export default new MockPackage({
  metadata: buildMetadata(26, 'Coinflip', data, {
    description: 'Flips a coin. Fails with a 500 error 50% of the time.',
  }),
  getResults() {
    if (Math.random() < 0.5) {
      throw new MockPackageError(500, 'coin_lost', 'The coin rolled under the couch and could not be found');
    }
    return { Coin: { side: Math.random() < 0.5 ? 'Heads' : 'Tails', flipped_at: new Date().toISOString() } };
  },
});
