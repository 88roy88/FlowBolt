import { describe, it, expect } from 'vitest';
import { paramLines } from '../dataSourceParams';

describe('paramLines', () => {
  it('lists each param with its cube', () => {
    const body = JSON.stringify({ sales: { region: 'north', ids: [1, 2] }, dates: { range: { From: 'a', To: 'b' } } });

    expect(paramLines(body)).toEqual([
      'sales.region: "north"',
      'sales.ids: [1,2]',
      'dates.range: {"From":"a","To":"b"}',
    ]);
  });

  it.each([null, '', '{}'])('has nothing to list for %j', (body) => {
    expect(paramLines(body)).toEqual([]);
  });

  it.each(['{"sales":{"reg…', '[1,2]', '{"limit":5}'])('shows %s as it is', (body) => {
    expect(paramLines(body)).toEqual([body]);
  });

  it('shortens long values', () => {
    const [line] = paramLines(JSON.stringify({ c: { p: 'x'.repeat(500) } }));

    expect(line.length).toBeLessThan(140);
    expect(line.endsWith('…')).toBe(true);
  });
});
