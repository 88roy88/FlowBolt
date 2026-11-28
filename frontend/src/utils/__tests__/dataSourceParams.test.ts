import { describe, it, expect } from 'vitest';
import { describeParams, formatBody } from '../dataSourceParams';

const labels = [
  { cube_id: 'sales', name: 'region', label: 'Sales region' },
  { cube_id: 'sales', name: 'date_range', label: 'Date' },
  { cube_id: 'stock', name: 'date', label: 'Date' },
];

const entries = (body: string | null) => {
  const result = describeParams(body, labels);
  if (!('entries' in result)) throw new Error('expected entries');
  return result.entries;
};

describe('describeParams', () => {
  it('labels each param by its cube and name, falling back to the name', () => {
    const body = JSON.stringify({ sales: { region: 'north', limit: 5 }, other: { region: 'x' } });

    expect(entries(body).map((e) => [e.label, e.path, e.value, e.ambiguous])).toEqual([
      ['Sales region', 'sales.region', '"north"', false],
      ['limit', 'sales.limit', '5', false],
      ['region', 'other.region', '"x"', false],
    ]);
  });

  it('marks params that share a label', () => {
    const body = JSON.stringify({ sales: { date_range: { From: 'a', To: 'b' }, region: 'n' }, stock: { date: 'c' } });

    expect(entries(body).map((e) => [e.label, e.ambiguous])).toEqual([
      ['Date', true],
      ['Sales region', false],
      ['Date', true],
    ]);
  });

  it.each([null, '', '{}'])('has nothing to list for %j', (body) => {
    expect(entries(body)).toEqual([]);
  });

  it.each(['{"sales":{"reg…', '[1,2]', '{"limit":5}'])('shows %s as it is', (body) => {
    expect(describeParams(body, labels)).toEqual({ raw: body });
  });

  it('shortens long values on screen', () => {
    const [entry] = entries(JSON.stringify({ c: { p: 'x'.repeat(500) } }));

    expect(entry.value.length).toBe(120);
    expect(entry.value.endsWith('…')).toBe(true);
  });
});

describe('formatBody', () => {
  it('indents the body without shortening or renaming anything', () => {
    const body = { sales: { region: 'x'.repeat(500) } };

    expect(formatBody(JSON.stringify(body))).toBe(JSON.stringify(body, null, 2));
  });
});
