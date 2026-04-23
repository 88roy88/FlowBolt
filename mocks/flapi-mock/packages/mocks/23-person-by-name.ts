import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';
import { people, peopleByName } from './_people.js';

// Shape the sample output as a single-row cube so buildMetadata emits a usable schema.
const sampleData = { person: [people[0]] };

export default new MockPackage({
  metadata: buildMetadata(23, 'Get Person by Name', sampleData, {
    description: 'Returns full profile and photo URL for a person matched by exact name.',
  }),
  quickParams: quickParamsQuery('person-by-name-query-1', [
    {
      name: 'name',
      displayName: 'Name',
      type: 'String',
      required: true,
      singleValue: true,
      description: 'Exact display name (case-insensitive).',
    },
  ]),
  getResults(quickParams) {
    const raw = quickParams?.name;
    const key = typeof raw === 'string' ? raw.trim().toLowerCase() : '';
    const match = key ? peopleByName.get(key) : undefined;
    if (!match) {
      return {
        person: [
          {
            name: `not found: ${typeof raw === 'string' ? raw : ''}`,
            title: '',
            department: '',
            email: '',
            phone: '',
            location: '',
            bio: '',
            image_url: '',
          },
        ],
      };
    }
    return { person: [match] };
  },
});
