import { MockPackage, quickParamsQuery, tag } from './package-base.js';

const data = {
  required_cube: [
    { id: 1, status: 'Active', count: 42 },
    { id: 2, status: 'Pending', count: 18 },
    { id: 3, status: 'Completed', count: 95 },
    { id: 4, status: 'Active', count: 27 },
    { id: 5, status: 'Pending', count: 33 },
    { id: 6, status: 'Completed', count: 12 },
  ],
};

export default new MockPackage({
  id: 14,
  name: 'Required Parameter Example',
  tags: [tag('Demo'), tag('Required')],
  quickParams: quickParamsQuery('required-query-1', 'Status Query', [
    {
      name: 'status',
      displayName: 'Status',
      type: 'String',
      values: ['Active', 'Pending', 'Completed'],
      required: true,
      description: 'Status filter (required)',
    },
  ]),
  getResults(body, extractQuickParams) {
    const params = extractQuickParams(body);
    const statusFilter = params?.status;

    if (!statusFilter) {
      return { required_cube: [] };
    }

    const statuses = Array.isArray(statusFilter) ? statusFilter : [statusFilter];
    return {
      required_cube: data.required_cube.filter((row) => statuses.includes(row.status)),
    };
  },
});
