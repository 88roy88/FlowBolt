import { MockPackage, tag } from './package-base.js';
import pkg01 from './01-sales.js';

export default new MockPackage({
  id: 2,
  name: 'User Analytics Package',
  tags: [tag('אפיון')],
  schema: pkg01.schema,
  getResults() {
    return pkg01.getResults();
  },
});
