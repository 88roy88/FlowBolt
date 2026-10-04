import { MockPackage, buildMetadata, quickParamsQuery } from '../package-base.js';

const peopleData = {
  1: { id: 'p12345', name: 'Ryan M' },
  2: { id: 'p22345', name: 'Nora T' },
  3: { id: 'p32345', name: 'Rachel K' },
  4: { id: 'p42345', name: 'Sam R' },
  5: { id: 'p52345', name: 'Owen C' },
};

const data = { Person: { id: 'p12345', name: 'Ryan M' } };

export default new MockPackage({
  metadata: buildMetadata(20, 'Get Person by ID', data),
  quickParams: quickParamsQuery('person-query-1', [
    {
      name: 'personId',
      displayName: 'Person ID',
      type: 'Int',
      defaultValues: [1],
      required: true,
      singleValue: true,
      description: 'The ID of the person to look up',
    },
  ]),
  getResults(quickParams) {
    const personId = quickParams?.personId as number | undefined;
    const person = personId ? peopleData[personId as keyof typeof peopleData] : undefined;
    return { Person: person || { id: 'not found', name: 'not found person for id ' + personId } };
  },
});
