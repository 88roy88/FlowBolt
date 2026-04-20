import { MockPackage, tag } from './package-base.js';

const peopleData = {
  1: { id: 'p12345', name: 'Roy M' },
  2: { id: 'p22345', name: 'Noa T' },
  3: { id: 'p32345', name: 'Rivky K' },
  4: { id: 'p42345', name: 'Shalom R' },
  5: { id: 'p52345', name: 'Ori C' },
};

export default new MockPackage({
  id: 20,
  name: 'Get Person by ID',
  tags: [tag('דוגמה')],
  schema: { Person: ['id', 'name'] },
  quickParams: {
    'person-query-1': [
      {
        Name: 'personId', ColumnName: 'person_id_col', Type: 'Integer', DisplayName: 'Person ID',
        IsSingleValue: true, IsRequired: true, Visible: true,
        Value: [
          { Name: '1', Value: '1' },
          { Name: '2', Value: '2' },
          { Name: '3', Value: '3' },
          { Name: '4', Value: '4' },
          { Name: '5', Value: '5' },
        ],
        IsDynamic: false, IsExcel: false, OntologyType: 'NUMBER', Attributes: [],
        id: 'Input_personId', data: {},
        quickParameterInfo: {
          DisplayName: 'Person ID', Description: 'The ID of the person to look up',
          RequiredType: { IsRequired: true, IsRequireAny: false, DisplayName: 'Required', disabledToolTipText: 'This parameter is required' },
        },
        parameterIndex: 1,
        QueryId: 'person-query-1', QueryDisplayName: 'Person Query',
      },
    ],
  },
  getResults(body, extractQuickParams) {
    const quickParams = extractQuickParams(body);
    const personId = quickParams?.personId;
    const person = peopleData[personId] || { id: 'not found', name: 'not found person for id ' + personId };
    return { Person: person };
  },
});
