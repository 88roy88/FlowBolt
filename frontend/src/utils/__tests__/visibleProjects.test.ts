import { describe, expect, it } from 'vitest';
import { getVisibleProjects } from '../visibleProjects';
import type { Project } from '../../types';

const p = (id: string) => ({ id, name: id }) as Project;
const ids = (list: Project[]) => list.map((x) => x.id);

describe('getVisibleProjects', () => {
  it('returns the loaded projects when there is no search or current project', () => {
    const projects = [p('a'), p('b')];
    expect(getVisibleProjects(projects, null, null)).toBe(projects);
  });

  it('pins a current project missing from the loaded pages at the top', () => {
    expect(ids(getVisibleProjects([p('a'), p('b')], null, p('x')))).toEqual(['x', 'a', 'b']);
  });

  it('leaves the list alone when the current project is already loaded', () => {
    const projects = [p('a'), p('b')];
    expect(getVisibleProjects(projects, null, p('b'))).toBe(projects);
  });

  it('returns only the search results while searching, without pinning', () => {
    const results = [p('a')];
    expect(getVisibleProjects([p('a'), p('b')], { results }, p('x'))).toBe(results);
  });
});
