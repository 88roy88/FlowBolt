import { MockPackage, quickParamsQuery, tag } from './package-base.js';

const data = {
  filters_cube: [
    { id: 1, region: 'North', department: 'Sales', metric: 850 },
    { id: 2, region: 'South', department: 'Marketing', metric: 620 },
    { id: 3, region: 'East', department: 'Sales', metric: 740 },
  ],
};

export default new MockPackage({
  id: 16,
  name: 'Require Any Parameter Example',
  tags: [tag('Demo'), tag('RequireAny')],
  quickParams: quickParamsQuery('requireany-query-1', 'Filters Query', [
    {
      name: 'region',
      displayName: 'Region',
      type: 'String',
      values: ['North', 'South', 'East', 'West'],
      requireAny: true,
      description: 'Filter by region (at least one value required)',
    },
  ]),
  getResults(body, extractQuickParams) {
    const params = extractQuickParams(body);
    const regionFilter = params?.region;

    if (!regionFilter) {
      return { filters_cube: [] };
    }

    const regions = Array.isArray(regionFilter) ? regionFilter : [regionFilter];
    return {
      filters_cube: data.filters_cube.filter((row) => regions.includes(row.region)),
    };
  },
});
