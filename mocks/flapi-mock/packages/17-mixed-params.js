import { MockPackage, quickParamsQuery, tag } from './package-base.js';

const data = {
  reports_cube: [
    { id: 1, type: 'Sales', quarter: 'Q1', year: 2025, active: true },
    { id: 2, type: 'Marketing', quarter: 'Q2', year: 2025, active: true },
    { id: 3, type: 'Finance', quarter: 'Q1', year: 2024, active: false },
  ],
};

export default new MockPackage({
  id: 17,
  name: 'Mixed Parameters Example',
  tags: [tag('Demo'), tag('Mixed')],
  quickParams: quickParamsQuery('mixed-query-1', 'Reports Query', [
    {
      name: 'type',
      displayName: 'Report Type',
      type: 'String',
      values: ['Sales', 'Marketing', 'Finance', 'Operations'],
      required: true,
      singleValue: true,
      description: 'Report type (required, single value)',
    },
    {
      name: 'quarter',
      displayName: 'Quarter',
      type: 'String',
      values: ['Q1', 'Q2', 'Q3', 'Q4'],
      required: false,
      description: 'Filter by quarter (optional, multi-select)',
    },
    {
      name: 'year',
      displayName: 'Year',
      type: 'Integer',
      values: [2024, 2025, 2026],
      requireAny: true,
      description: 'Filter by year (at least one required)',
    },
    {
      name: 'active',
      displayName: 'Active Only',
      type: 'Boolean',
      values: [true, false],
      required: false,
      singleValue: true,
      description: 'Show only active reports (optional)',
    },
  ]),
  getResults(body, extractQuickParams) {
    const params = extractQuickParams(body);
    let results = [...data.reports_cube];

    // Required: type
    if (params?.type) {
      results = results.filter((row) => row.type === params.type);
    } else {
      return { reports_cube: [] };
    }

    // Optional: quarter
    if (params?.quarter) {
      const quarters = Array.isArray(params.quarter) ? params.quarter : [params.quarter];
      results = results.filter((row) => quarters.includes(row.quarter));
    }

    // RequireAny: year
    if (params?.year) {
      const years = Array.isArray(params.year) ? params.year : [params.year];
      results = results.filter((row) => years.includes(row.year));
    } else {
      return { reports_cube: [] };
    }

    // Optional: active
    if (params?.active !== undefined) {
      results = results.filter((row) => row.active === params.active);
    }

    return { reports_cube: results };
  },
});
