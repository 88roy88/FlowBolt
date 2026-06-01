import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';
import { people } from './_people.js';

// 1-indexed into the shared roster so ids line up with what a user can see in
// `_people.ts`. Exercises the multi-value (`singleValue: false`) path.
const sampleData = { people: [people[0]] };

export default new MockPackage({
  metadata: buildMetadata(24, 'Get People by IDs', sampleData, {
    description: 'Returns full profiles for the given list of person IDs (1-based index into the roster).',
  }),
  quickParams: quickParamsQuery('people-by-ids-query-1', [
    {
      name: 'personIds',
      displayName: 'Person IDs',
      type: 'Int',
      required: true,
      singleValue: false,
      defaultValues: [1, 2, 3],
      description: 'One or more 1-based person IDs to look up.',
    },
  ]),
  getResults(quickParams) {
    const raw = quickParams?.personIds;
    const ids = Array.isArray(raw) ? raw : raw !== undefined ? [raw] : [];
    const results = ids.map((idValue) => {
      const id = typeof idValue === 'number' ? idValue : Number(idValue);
      const person = Number.isFinite(id) ? people[id - 1] : undefined;
      return (
        person ?? {
          name: `not found: ${idValue}`,
          title: '',
          department: '',
          email: '',
          phone: '',
          location: '',
          bio: '',
          image_url: '',
        }
      );
    });
    return { people: results };
  },
});
