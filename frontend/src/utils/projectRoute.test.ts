import { describe, expect, it } from 'vitest';
import {
  getProjectIdFromHash,
  isKnownProjectId,
  resolveRouteAction,
} from './projectRoute';
import type { Project } from '../types';

const projects: Project[] = [
  { id: 'aaa', name: 'A', created_at: '2024-01-01T00:00:00Z' },
  { id: 'bbb', name: 'B', created_at: '2024-01-02T00:00:00Z' },
];

describe('getProjectIdFromHash', () => {
  it('parses project id from hash', () => {
    expect(getProjectIdFromHash('#/project/aaa')).toBe('aaa');
  });

  it('returns null when hash is missing or malformed', () => {
    expect(getProjectIdFromHash('')).toBeNull();
    expect(getProjectIdFromHash('#/project/')).toBeNull();
    expect(getProjectIdFromHash('#/other/aaa')).toBeNull();
  });
});

describe('resolveRouteAction', () => {
  it('redirects home for unknown project id once projects are loaded', () => {
    expect(
      resolveRouteAction({
        hashProjectId: 'missing',
        projects,
        loading: false,
        currentProjectId: null,
      }),
    ).toEqual({ type: 'redirect_home' });
  });

  it('redirects home for unknown id even while loading flag is true', () => {
    expect(
      resolveRouteAction({
        hashProjectId: 'missing',
        projects,
        loading: true,
        currentProjectId: null,
      }),
    ).toEqual({ type: 'redirect_home' });
  });

  it('auto-selects first project on bare home url', () => {
    expect(
      resolveRouteAction({
        hashProjectId: null,
        projects,
        loading: false,
        currentProjectId: null,
      }),
    ).toEqual({ type: 'select_project', project: projects[0] });
  });

  it('does not auto-select when a project is already selected', () => {
    expect(
      resolveRouteAction({
        hashProjectId: null,
        projects,
        loading: false,
        currentProjectId: 'bbb',
      }),
    ).toEqual({ type: 'none' });
  });
});

describe('isKnownProjectId', () => {
  it('returns true for ids in the list', () => {
    expect(isKnownProjectId('aaa', projects)).toBe(true);
  });

  it('returns false for unknown ids', () => {
    expect(isKnownProjectId('missing', projects)).toBe(false);
  });
});
