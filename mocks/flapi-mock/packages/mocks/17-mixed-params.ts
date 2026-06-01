import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const data = {
  reports_cube: [
    { id: 1, type: 'Sales', quarter: 'Q1', year: 2025, region: 'North', department: 'Retail', priority: 'High' },
    { id: 2, type: 'Marketing', quarter: 'Q2', year: 2025, region: 'South', department: 'Digital', priority: 'Medium' },
    { id: 3, type: 'Finance', quarter: 'Q1', year: 2024, region: 'East', department: 'Analytics', priority: 'Low' },
    { id: 4, type: 'Sales', quarter: 'Q3', year: 2025, region: 'West', department: 'Wholesale', priority: 'High' },
    { id: 5, type: 'Operations', quarter: 'Q4', year: 2024, region: 'North', department: 'Logistics', priority: 'Critical' },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(17, 'Mixed Parameters Example - All Constraint Types', data),
  quickParams: quickParamsQuery('mixed-query-1', [
    {
      name: 'type',
      displayName: 'Report Type',
      type: 'String',
      required: true,
      singleValue: true,
      description: 'Report type (required, no default)',
    },
    {
      name: 'quarter',
      displayName: 'Quarter',
      type: 'String',
      defaultValues: ['Q1'],
      singleValue: true,
      required: true,
      description: 'Quarter (required with default)',
    },
    {
      name: 'priority',
      displayName: 'Priority Filter',
      type: 'String',
      singleValue: false,
      required: false,
      description: 'Priority levels (optional, multi-select)',
    },
    {
      name: 'region',
      displayName: 'Region',
      type: 'String',
      singleValue: false,
      requireAny: true,
      description: 'Filter by region (requireAny group)',
    },
    {
      name: 'department',
      displayName: 'Department',
      type: 'String',
      singleValue: false,
      requireAny: true,
      description: 'Filter by department (requireAny group)',
    },
  ]),
  getResults(quickParams) {
    let results = [...data.reports_cube];

    // Required (no default): type
    if (quickParams?.type) {
      results = results.filter((row) => row.type === quickParams.type);
    }

    // Required (with default): quarter
    if (quickParams?.quarter) {
      results = results.filter((row) => row.quarter === quickParams.quarter);
    }

    // Optional: priority
    if (quickParams?.priority) {
      const priorities = Array.isArray(quickParams.priority) ? quickParams.priority : [quickParams.priority];
      results = results.filter((row) => priorities.includes(row.priority));
    }

    // RequireAny group: region or department
    const hasRegion = quickParams?.region;
    const hasDepartment = quickParams?.department;

    if (hasRegion) {
      const regions = Array.isArray(quickParams.region) ? quickParams.region : [quickParams.region];
      results = results.filter((row) => regions.includes(row.region));
    }

    if (hasDepartment) {
      const departments = Array.isArray(quickParams.department) ? quickParams.department : [quickParams.department];
      results = results.filter((row) => departments.includes(row.department));
    }

    return { reports_cube: results };
  },
});
