import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

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
  metadata: buildMetadata(14, 'Required Parameter Example', data),
  quickParams: quickParamsQuery('required-query-1', [
    {
      name: 'status',
      displayName: 'Status',
      type: 'String',
      defaultValues: ['Active'],
      required: true,
      description: 'Status filter (required with default)',
    },
  ]),
  getResults(quickParams) {
    const statusFilter = quickParams?.status;

    if (!statusFilter) {
      return { required_cube: [] };
    }

    const statuses = Array.isArray(statusFilter) ? statusFilter : [statusFilter];
    return {
      required_cube: data.required_cube.filter((row) => statuses.includes(row.status)),
    };
  },
});
