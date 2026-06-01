import { MockPackage, buildMetadata } from '../package-base.js';

const data = {
  people: [
    { id: 'p1', m_id:1, hebrew_name: 'אלכס חן', department: 'הנדסה', rank: 'סגן' },
    { id: 'p2', m_id:2, hebrew_name: 'סם ריברה', department: 'מודיעין', rank: 'סרן' },
    { id: 'p3', m_id:3, hebrew_name: 'ג\'ורדן לי', department: 'לוגיסטיקה', rank: 'רב-סרן' },
    { id: 'p4', m_id:4, hebrew_name: 'קייסי מורגן', department: 'תקשוב', rank: 'סגן' },
    { id: 'p5', m_id:5, hebrew_name: 'ריילי טיילור', department: 'הנדסה', rank: 'סרן' },
    { id: 'p6', m_id:6, hebrew_name: 'קווין אדמס', department: 'מבצעים', rank: 'רב-סרן' },
    { id: 'p7', m_id:7, hebrew_name: 'רבקה מ', department: 'מודיעין', rank: 'סגן-אלוף' },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(6, 'People Hebrew Names', data, {
    description: 'Hebrew names for people (same IDs as People & Photos)',
  }),
  getResults: () => data,
});
