import { describe, it, expect, beforeEach } from 'vitest';
import { handleDataSourceMessage, MAX_RECENT_CALLS, useDataSourceActivityStore } from '../dataSourceActivity';

const start = (callId: string, params: string | null = null) =>
  handleDataSourceMessage({ type: 'data-source-call', phase: 'start', dataSourceId: '12', callId, params });
const end = (callId: string, result: string) =>
  handleDataSourceMessage({ type: 'data-source-call', phase: 'end', dataSourceId: '12', callId, result });
const activity = () => useDataSourceActivityStore.getState().byId['12'];

describe('data source activity', () => {
  beforeEach(() => useDataSourceActivityStore.getState().reset());

  it('stays running until every overlapping call ends', () => {
    start('a', '{"cube":{}}');
    start('b');
    end('a', 'error');

    expect(activity()).toMatchObject({ count: 2, running: ['b'], lastResult: 'error' });
    expect(activity().recent.map((c) => [c.id, c.result, c.params])).toEqual([
      ['b', 'running', null],
      ['a', 'error', '{"cube":{}}'],
    ]);
  });

  it('keeps only the newest calls while counting all of them', () => {
    for (let i = 0; i <= MAX_RECENT_CALLS; i++) start(`call-${i}`);

    expect(activity().count).toBe(MAX_RECENT_CALLS + 1);
    expect(activity().recent).toHaveLength(MAX_RECENT_CALLS);
    expect(activity().recent[0].id).toBe(`call-${MAX_RECENT_CALLS}`);
  });

  it('keeps the previous result when a call is cancelled', () => {
    start('a');
    end('a', 'ok');
    start('b');
    end('b', 'aborted');

    expect(activity()).toMatchObject({ running: [], lastResult: 'ok' });
  });

  it('stops waiting for calls once the preview is gone', () => {
    start('a');
    useDataSourceActivityStore.getState().clearRunning();
    end('a', 'ok');

    expect(activity()).toMatchObject({ count: 1, running: [], lastResult: null });
    expect(activity().recent[0].result).toBe('aborted');
  });

  it('starts over when the preview loads a new document', () => {
    start('a');
    expect(handleDataSourceMessage({ type: 'data-source-reset' })).toBe(true);
    end('a', 'ok');

    expect(useDataSourceActivityStore.getState().byId).toEqual({});
  });

  it('leaves other toolbar messages to the bridge', () => {
    expect(handleDataSourceMessage({ type: 'hello' })).toBe(false);
  });
});
