import { MockPackage, buildMetadata } from '../package-base.js';

const data = {
  people: [
    { id: 'p1', name: 'Alex Chen', phone: '+1-555-201-1001', last_seen_location: 'Building A, Floor 3', image_url: 'https://picsum.photos/seed/p1/400/400' },
    { id: 'p2', name: 'Sam Rivera', phone: '+1-555-201-1002', last_seen_location: 'Cafeteria', image_url: 'https://picsum.photos/seed/p2/400/400' },
    { id: 'p3', name: 'Jordan Lee', phone: '+1-555-201-1003', last_seen_location: 'Conference Room B', image_url: 'https://picsum.photos/seed/p3/400/400' },
    { id: 'p4', name: 'Casey Morgan', phone: '+1-555-201-1004', last_seen_location: 'Main Office', image_url: 'https://picsum.photos/seed/p4/400/400' },
    { id: 'p5', name: 'Riley Taylor', phone: '+1-555-201-1005', last_seen_location: 'Lab 2', image_url: 'https://picsum.photos/seed/p5/400/400' },
    { id: 'p6', name: 'Quinn Adams', phone: '+1-555-201-1006', last_seen_location: 'Parking Lot', image_url: 'https://picsum.photos/seed/p6/400/400' },
    { id: 'p7', name: 'Rivky K', phone: '+1-555-201-1006', last_seen_location: 'Parking Lot', image_url: 'https://picsum.photos/seed/p7/400/400' },
  ],
  photos: [
    { id: 'img1', photo_id: 'p1', url: 'https://picsum.photos/seed/p1/400/400', caption: 'Alex Chen' },
    { id: 'img2', photo_id: 'p2', url: 'https://picsum.photos/seed/p2/400/400', caption: 'Sam Rivera' },
    { id: 'img3', photo_id: 'p3', url: 'https://picsum.photos/seed/p3/400/400', caption: 'Jordan Lee' },
    { id: 'img4', photo_id: 'p4', url: 'https://picsum.photos/seed/p4/400/400', caption: 'Casey Morgan' },
    { id: 'img5', photo_id: 'p5', url: 'https://picsum.photos/seed/p5/400/400', caption: 'Riley Taylor' },
    { id: 'img6', photo_id: 'p6', url: 'https://picsum.photos/seed/p6/400/400', caption: 'Quinn Adams' },
    { id: 'img7', photo_id: 'p7', url: 'https://picsum.photos/seed/p7/400/400', caption: 'Quinn Adams' },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(4, 'People & Photos', data),
  getResults: () => data,
});
