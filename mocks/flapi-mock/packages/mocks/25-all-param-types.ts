import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const sampleData = {
  echo: [
    {
      label: 'sample text',
      date_range: '2025-01-01',
      recorded_at: '2025-01-01T00:00:00Z',
      area: 'POINT(0 0)',
      is_active: true,
      count: 42,
    },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(25, 'All Parameter Types — Echo', sampleData, {
    description: 'Exercises all parameter values types and returns whatever values were passed in.',
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
    {
      name: 'is_active',
      displayName: 'Is active',
      type: 'Boolean',
      required: false,
      singleValue: true,
      description: 'A boolean flag (BooleanValue).',
    },
    {
      name: 'count',
      displayName: 'Count',
      type: 'Int',
      required: false,
      singleValue: true,
      description: 'An integer value.',
    },
  ]),
  getResults(quickParams) {
    const extractString = (v: unknown): string | null => {
      if (v == null) return null;
      if (typeof v === 'string') return v;
      if (Array.isArray(v) && v.length > 0) {
        const first = v[0];
        if (typeof first === 'string') return first;
        if (typeof first === 'object' && first != null && 'Value' in first) return String((first as { Value: unknown }).Value);
      }
      return null;
    };
    const extractInt = (v: unknown): number | null => {
      if (v == null) return null;
      if (typeof v === 'number') return Math.trunc(v);
      if (Array.isArray(v) && v.length > 0) {
        const first = v[0];
        if (typeof first === 'number') return Math.trunc(first);
        if (typeof first === 'object' && first != null && 'Value' in first) return Math.trunc(Number((first as { Value: unknown }).Value));
      }
      return null;
    };

    const label = extractString(quickParams.label);

    const date_range = (() => {
      if (quickParams.date_range == null) return null;
      const d = quickParams.date_range as
        | { From: string; To: string }
        | { TimeBackValue: number; TimeBackUnit: string };
      return 'To' in d ? d.To : new Date().toISOString().slice(0, 10);
    })();

    const recorded_at =
      quickParams.recorded_at != null ? JSON.stringify(quickParams.recorded_at) : null;

    const area = Array.isArray(quickParams.area)
      ? ((quickParams.area as { value: string[]; radius: number }[])[0]?.value?.[0] ?? null)
      : null;

    const is_active =
      quickParams.is_active != null ? Boolean(quickParams.is_active) : null;

    const count = extractInt(quickParams.count);

    return { echo: [{ label, date_range, recorded_at, area, is_active, count }] };
  },
});
