import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const sampleData = {
  echo: [
    {
      label: 'sample text',
      date_range: '2025-01-01',
      recorded_at: '2025-01-01T00:00:00Z',
      area: 'POINT(0 0)',
    },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(25, 'All Parameter Types — Echo', sampleData, {
    description: 'Exercises all four FlowParam value types (TextValue, DateRangeValue, TimestampValue, GeographicValue). Returns whatever values were passed in.',
  }),
  quickParams: quickParamsQuery('echo-query-1', [
    {
      name: 'label',
      displayName: 'Label',
      type: 'String',
      required: true,
      singleValue: true,
      description: 'A text value (TextValue).',
    },
    {
      name: 'date_range',
      displayName: 'Date range',
      type: 'DateTime',
      required: true,
      singleValue: true,
      description: 'A date-range value (DateRangeValue).',
    },
    {
      name: 'recorded_at',
      displayName: 'Recorded at',
      type: 'Timestamp',
      required: false,
      singleValue: true,
      description: 'A relative or absolute timestamp (TimestampValue).',
    },
    {
      name: 'area',
      displayName: 'Area',
      type: 'Haphoch',
      required: false,
      singleValue: true,
      description: 'A geographic area in WKT (GeographicValue).',
    },
  ]),
  getResults(quickParams) {
    return {
      echo: [
        {
          label: quickParams.label ?? null,
          date_range: quickParams.date_range ?? null,
          recorded_at: quickParams.recorded_at ?? null,
          area: quickParams.area ?? null,
        },
      ],
    };
  },
});
