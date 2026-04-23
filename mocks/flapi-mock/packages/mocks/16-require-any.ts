import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const data = {
  filters_cube: [
    { id: 1, region: 'North', department: 'Sales', status: 'Active', metric: 850 },
    { id: 2, region: 'South', department: 'Marketing', status: 'Active', metric: 620 },
    { id: 3, region: 'East', department: 'Sales', status: 'Inactive', metric: 740 },
    { id: 4, region: 'West', department: 'Engineering', status: 'Active', metric: 920 },
    { id: 5, region: 'North', department: 'Marketing', status: 'Inactive', metric: 580 },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(16, 'Require Any Parameter Example', data),
  quickParams: quickParamsQuery('requireany-query-1', [
    {
      name: 'region',
      displayName: 'Region',
      type: 'String',
      singleValue: false,
      requireAny: true,
      description: 'Filter by region (at least one value required)',
    },
    {
      name: 'department',
      displayName: 'Department',
      type: 'String',
      singleValue: false,
      requireAny: true,
      description: 'Filter by department (at least one value required)',
    },
  ]),
  getResults(quickParams) {
    const regionFilter = quickParams?.region;
    const departmentFilter = quickParams?.department;

    if (!regionFilter && !departmentFilter) {
      return { filters_cube: [] };
    }

    const regions = regionFilter ? (Array.isArray(regionFilter) ? regionFilter : [regionFilter]) : null;
    const departments = departmentFilter ? (Array.isArray(departmentFilter) ? departmentFilter : [departmentFilter]) : null;

    return {
      filters_cube: data.filters_cube.filter((row) => {
        const matchesRegion = !regions || regions.includes(row.region);
        const matchesDept = !departments || departments.includes(row.department);
        return matchesRegion && matchesDept;
      }),
    };
  },
});
