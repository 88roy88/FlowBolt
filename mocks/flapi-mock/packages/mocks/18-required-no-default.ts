import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const data = {
  required_cube: [
    { id: 1, status: 'Active', count: 42 },
    { id: 2, status: 'Pending', count: 18 },
    { id: 3, status: 'Completed', count: 95 },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(18, 'Required Parameter Without Default', data),
  quickParams: quickParamsQuery('required-query-18', [
    {
      name: 'status',
      displayName: 'Status',
      type: 'String',
      required: true,
      description: 'Status filter (required, no default)',
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
