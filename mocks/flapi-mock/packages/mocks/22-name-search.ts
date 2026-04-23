import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';
import { people } from './_people.js';

const data = { names: people.map((p) => ({ name: p.name })) };

export default new MockPackage({
  metadata: buildMetadata(22, 'Search Names by Prefix', data, {
    description: 'Returns names whose first characters match a given prefix.',
  }),
  quickParams: quickParamsQuery('name-search-query-1', [
    {
      name: 'namePrefix',
      displayName: 'Name Prefix',
      type: 'String',
      required: false,
      singleValue: true,
      defaultValues: [''],
      description: 'Case-insensitive prefix to match against names. Empty returns all.',
    },
  ]),
  getResults(quickParams) {
    const raw = quickParams?.namePrefix;
    const prefix = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
    if (!prefix) return data;
    return {
      names: data.names.filter((row) => row.name.toLowerCase().startsWith(prefix)),
    };
  },
});
