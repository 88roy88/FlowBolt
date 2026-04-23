import { MockPackage, quickParamsQuery, buildMetadata } from '../package-base.js';

const data = {
  products_cube: [
    { id: 1, name: 'Widget A', category: 'Electronics', price: 299 },
    { id: 2, name: 'Widget B', category: 'Home', price: 149 },
    { id: 3, name: 'Widget C', category: 'Electronics', price: 499 },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(15, 'Optional Parameters Example', data),
  quickParams: quickParamsQuery('optional-query-1', [
    {
      name: 'category',
      displayName: 'Category',
      type: 'String',
      defaultValues: ['Electronics', 'Home'],
      singleValue: false,
      required: false,
      description: 'Filter by category (optional with defaults)',
    },
    {
      name: 'minPrice',
      displayName: 'Min Price',
      type: 'Integer',
      defaultValues: [0],
      required: false,
      singleValue: true,
      description: 'Minimum price filter (optional with default)',
    },
  ]),
  getResults(quickParams) {
    let results = [...data.products_cube];

    if (quickParams?.category) {
      const categories = Array.isArray(quickParams.category) ? quickParams.category : [quickParams.category];
      results = results.filter((row) => categories.includes(row.category));
    }

    if (quickParams?.minPrice !== undefined) {
      const minPrice = Number(quickParams.minPrice);
      results = results.filter((row) => row.price >= minPrice);
    }

    return { products_cube: results };
  },
});
