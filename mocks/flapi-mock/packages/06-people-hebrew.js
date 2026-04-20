import { MockPackage, tag } from './package-base.js';

const data = {
  people: [
    { id: 'p1', hebrew_name: 'אלכס חן', department: 'הנדסה', rank: 'סגן' },
    { id: 'p2', hebrew_name: 'סם ריברה', department: 'מודיעין', rank: 'סרן' },
    { id: 'p3', hebrew_name: 'ג\'ורדן לי', department: 'לוגיסטיקה', rank: 'רב-סרן' },
    { id: 'p4', hebrew_name: 'קייסי מורגן', department: 'תקשוב', rank: 'סגן' },
    { id: 'p5', hebrew_name: 'ריילי טיילור', department: 'הנדסה', rank: 'סרן' },
    { id: 'p6', hebrew_name: 'קווין אדמס', department: 'מבצעים', rank: 'רב-סרן' },
    { id: 'p7', hebrew_name: 'רבקה מ', department: 'מודיעין', rank: 'סגן-אלוף' },
  ],
};

export default new MockPackage({
  id: 6,
  name: 'People Hebrew Names',
  tags: [tag('אנשים'), tag('עברית')],
  description: 'Hebrew names for people (same IDs as People & Photos)',
  data,
});
