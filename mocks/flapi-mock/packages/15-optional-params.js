import { MockPackage, quickParamsQuery, tag } from './package-base.js';

const data = {
  products_cube: [
    { id: 1, name: 'Widget A', category: 'Electronics', price: 299 },
    { id: 2, name: 'Widget B', category: 'Home', price: 149 },
    { id: 3, name: 'Widget C', category: 'Electronics', price: 499 },
  ],
};

export default new MockPackage({
  id: 15,
  name: 'Optional Parameters Example',
  tags: [tag('Demo'), tag('Optional')],
  quickParams: quickParamsQuery('optional-query-1', 'Products Query', [
    {
      name: 'category',
      displayName: 'Category',
      type: 'String',
      values: ['Electronics', 'Home', 'Garden', 'Sports'],
      required: false,
      description: 'Filter by category (optional)',
    },
    {
      name: 'minPrice',
      displayName: 'Min Price',
      type: 'Integer',
      values: [0, 100, 200, 500],
      required: false,
      singleValue: true,
      description: 'Minimum price filter (optional)',
    },
  ]),
  getResults(body, extractQuickParams) {
    const params = extractQuickParams(body);
    let results = [...data.products_cube];

    if (params?.category) {
      const categories = Array.isArray(params.category) ? params.category : [params.category];
      results = results.filter((row) => categories.includes(row.category));
    }

    if (params?.minPrice !== undefined) {
      results = results.filter((row) => row.price >= params.minPrice);
    }

    return { products_cube: results };
  },
});
