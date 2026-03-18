/** Stub package run results for Flapi mock (server-spec §2.1).
 *  Shared fields across cubes: customer_id, name, region, product, store_id, date.
 *  Each cube provides a different business perspective on the same sales domain. */
export const stubPackageResults = {
  sales_cube: [
    { id: 1,  customer_id: 'C001', name: 'Alice', region: 'North', store_id: 'S01', product: 'Widget A', amount: 100, quantity: 5,  date: '2025-01-15', channel: 'Online' },
    { id: 2,  customer_id: 'C002', name: 'Bob',   region: 'South', store_id: 'S02', product: 'Widget B', amount: 150, quantity: 3,  date: '2025-01-16', channel: 'Retail' },
    { id: 3,  customer_id: 'C003', name: 'Carol', region: 'East',  store_id: 'S03', product: 'Widget A', amount: 80,  quantity: 2,  date: '2025-01-17', channel: 'Online' },
    { id: 4,  customer_id: 'C004', name: 'Dan',   region: 'West',  store_id: 'S04', product: 'Widget C', amount: 200, quantity: 10, date: '2025-01-18', channel: 'Wholesale' },
    { id: 5,  customer_id: 'C001', name: 'Alice', region: 'North', store_id: 'S01', product: 'Widget B', amount: 120, quantity: 4,  date: '2025-02-01', channel: 'Retail' },
    { id: 6,  customer_id: 'C005', name: 'Eve',   region: 'South', store_id: 'S02', product: 'Widget C', amount: 90,  quantity: 1,  date: '2025-02-05', channel: 'Online' },
    { id: 7,  customer_id: 'C002', name: 'Bob',   region: 'East',  store_id: 'S03', product: 'Widget B', amount: 175, quantity: 7,  date: '2025-02-10', channel: 'Wholesale' },
    { id: 8,  customer_id: 'C006', name: 'Frank', region: 'West',  store_id: 'S04', product: 'Widget A', amount: 60,  quantity: 2,  date: '2025-02-14', channel: 'Retail' },
    { id: 9,  customer_id: 'C003', name: 'Carol', region: 'North', store_id: 'S01', product: 'Widget C', amount: 310, quantity: 6,  date: '2025-03-01', channel: 'Wholesale' },
    { id: 10, customer_id: 'C001', name: 'Alice', region: 'South', store_id: 'S02', product: 'Widget A', amount: 140, quantity: 7,  date: '2025-03-05', channel: 'Online' },
    { id: 11, customer_id: 'C004', name: 'Dan',   region: 'East',  store_id: 'S03', product: 'Widget C', amount: 95,  quantity: 3,  date: '2025-03-08', channel: 'Retail' },
    { id: 12, customer_id: 'C005', name: 'Eve',   region: 'West',  store_id: 'S04', product: 'Widget B', amount: 220, quantity: 8,  date: '2025-03-12', channel: 'Online' },
  ],
  customers_cube: [
    { customer_id: 'C001', name: 'Alice', region: 'North', age: 34, gender: 'F', segment: 'Premium',  loyalty_points: 4800, signup_date: '2023-03-10' },
    { customer_id: 'C002', name: 'Bob',   region: 'South', age: 28, gender: 'M', segment: 'Standard', loyalty_points: 1200, signup_date: '2023-06-22' },
    { customer_id: 'C003', name: 'Carol', region: 'East',  age: 45, gender: 'F', segment: 'Premium',  loyalty_points: 6200, signup_date: '2022-11-05' },
    { customer_id: 'C004', name: 'Dan',   region: 'West',  age: 31, gender: 'M', segment: 'Basic',    loyalty_points: 450,  signup_date: '2024-01-18' },
    { customer_id: 'C005', name: 'Eve',   region: 'South', age: 39, gender: 'F', segment: 'Standard', loyalty_points: 2100, signup_date: '2023-09-30' },
    { customer_id: 'C006', name: 'Frank', region: 'West',  age: 52, gender: 'M', segment: 'Premium',  loyalty_points: 5500, signup_date: '2022-07-14' },
    { customer_id: 'C007', name: 'Grace', region: 'East',  age: 26, gender: 'F', segment: 'Basic',    loyalty_points: 320,  signup_date: '2024-05-02' },
    { customer_id: 'C008', name: 'Hank',  region: 'North', age: 41, gender: 'M', segment: 'Standard', loyalty_points: 1800, signup_date: '2023-12-11' },
  ],
  products_cube: [
    { product: 'Widget A', category: 'Electronics', brand: 'TechCo',  unit_price: 20.00, cost: 12.00, margin: 0.40, weight_kg: 0.5,  rating: 4.5 },
    { product: 'Widget B', category: 'Accessories', brand: 'GadgetX', unit_price: 30.00, cost: 15.00, margin: 0.50, weight_kg: 0.3,  rating: 4.1 },
    { product: 'Widget C', category: 'Services',    brand: 'ServPro', unit_price: 50.00, cost: 20.00, margin: 0.60, weight_kg: 0.0,  rating: 4.7 },
  ],
  stores_cube: [
    { store_id: 'S01', store_name: 'North Plaza',    region: 'North', city: 'Tel Aviv',   type: 'Flagship', size_sqm: 500, employees: 25, open_date: '2020-06-01' },
    { store_id: 'S02', store_name: 'South Mall',     region: 'South', city: 'Beer Sheva', type: 'Standard', size_sqm: 300, employees: 15, open_date: '2021-03-15' },
    { store_id: 'S03', store_name: 'East Center',    region: 'East',  city: 'Haifa',      type: 'Standard', size_sqm: 280, employees: 12, open_date: '2021-09-20' },
    { store_id: 'S04', store_name: 'West Outlet',    region: 'West',  city: 'Jerusalem',  type: 'Outlet',   size_sqm: 400, employees: 18, open_date: '2019-11-10' },
    { store_id: 'S05', store_name: 'Online Store',   region: 'All',   city: 'N/A',        type: 'Online',   size_sqm: 0,   employees: 8,  open_date: '2018-01-01' },
  ],
  inventory_cube: [
    { store_id: 'S01', store_name: 'North Plaza',  region: 'North', product: 'Widget A', stock: 340, reorder_level: 100, last_restock: '2025-02-20' },
    { store_id: 'S01', store_name: 'North Plaza',  region: 'North', product: 'Widget B', stock: 150, reorder_level: 80,  last_restock: '2025-03-05' },
    { store_id: 'S01', store_name: 'North Plaza',  region: 'North', product: 'Widget C', stock: 400, reorder_level: 150, last_restock: '2025-03-10' },
    { store_id: 'S02', store_name: 'South Mall',   region: 'South', product: 'Widget A', stock: 120, reorder_level: 100, last_restock: '2025-01-30' },
    { store_id: 'S02', store_name: 'South Mall',   region: 'South', product: 'Widget B', stock: 60,  reorder_level: 80,  last_restock: '2025-02-10' },
    { store_id: 'S02', store_name: 'South Mall',   region: 'South', product: 'Widget C', stock: 75,  reorder_level: 150, last_restock: '2025-02-28' },
    { store_id: 'S03', store_name: 'East Center',  region: 'East',  product: 'Widget A', stock: 85,  reorder_level: 100, last_restock: '2025-03-01' },
    { store_id: 'S03', store_name: 'East Center',  region: 'East',  product: 'Widget B', stock: 200, reorder_level: 80,  last_restock: '2025-03-08' },
    { store_id: 'S03', store_name: 'East Center',  region: 'East',  product: 'Widget C', stock: 160, reorder_level: 150, last_restock: '2025-03-02' },
    { store_id: 'S04', store_name: 'West Outlet',  region: 'West',  product: 'Widget A', stock: 210, reorder_level: 100, last_restock: '2025-02-15' },
    { store_id: 'S04', store_name: 'West Outlet',  region: 'West',  product: 'Widget B', stock: 90,  reorder_level: 80,  last_restock: '2025-01-25' },
    { store_id: 'S04', store_name: 'West Outlet',  region: 'West',  product: 'Widget C', stock: 310, reorder_level: 150, last_restock: '2025-03-12' },
  ],
};

/** Intelligence-style stub for package 3: reports, entities, events, indicators. */
export const stubIntelligenceResults = {
  reports: [
    { id: 'RPT-001', title: 'Weekly Threat Assessment', classification: 'SECRET', date: '2025-03-10', summary: 'Rising activity in sector 7; three new entities linked to campaign Alpha.', source: 'OSINT' },
    { id: 'RPT-002', title: 'Entity Network Mapping', classification: 'CONFIDENTIAL', date: '2025-03-12', summary: 'Mapping of 12 entities and 8 events; cross-ref with financial indicators.', source: 'HUMINT' },
    { id: 'RPT-003', title: 'Indicator Bulletin', classification: 'RESTRICTED', date: '2025-03-14', summary: 'New IOCs associated with infrastructure; recommend blocking at perimeter.', source: 'SIGINT' },
    { id: 'RPT-004', title: 'Quarterly Strategic Summary', classification: 'CONFIDENTIAL', date: '2025-03-08', summary: 'Regional posture and key findings from HUMINT and SIGINT fusion.', source: 'FUSION' },
    { id: 'RPT-005', title: 'Infrastructure Deep Dive', classification: 'SECRET', date: '2025-03-11', summary: 'Technical analysis of Server Farm 7 and related C2 infrastructure.', source: 'SIGINT' },
    { id: 'RPT-006', title: 'Person-of-Interest Update', classification: 'RESTRICTED', date: '2025-03-13', summary: 'Movement and communications pattern for primary subject.', source: 'HUMINT' },
  ],
  entities: [
    { name: 'Alpha Corp', type: 'Organization', country: 'N/A', role: 'Suspected front', links: 4 },
    { name: 'John D.', type: 'Person', country: 'XX', role: 'Key contact', links: 2 },
    { name: 'Server Farm 7', type: 'Infrastructure', country: 'YY', role: 'Hosting', links: 12 },
    { name: 'Campaign Alpha', type: 'Campaign', country: 'N/A', role: 'Active op', links: 8 },
    { name: 'Delta Holdings', type: 'Organization', country: 'ZZ', role: 'Shell entity', links: 3 },
    { name: 'Jane M.', type: 'Person', country: 'XX', role: 'Finance', links: 5 },
    { name: 'Relay Node A', type: 'Infrastructure', country: 'YY', role: 'Proxy', links: 7 },
    { name: 'Operation Beta', type: 'Campaign', country: 'N/A', role: 'Dormant', links: 2 },
  ],
  events: [
    { date: '2025-03-01', location: 'Region A', type: 'Meeting', description: 'Stakeholder coordination' },
    { date: '2025-03-05', location: 'Online', type: 'Transfer', description: 'Funds moved to shell entity' },
    { date: '2025-03-09', location: 'Region B', type: 'Deployment', description: 'New infrastructure detected' },
    { date: '2025-03-12', location: 'N/A', type: 'Report', description: 'Assessment published internally' },
    { date: '2025-03-02', location: 'Capital', type: 'Meeting', description: 'Briefing to leadership' },
    { date: '2025-03-06', location: 'Online', type: 'Transfer', description: 'Secondary transfer to Delta' },
    { date: '2025-03-10', location: 'Region C', type: 'Deployment', description: 'Mirror site activation' },
    { date: '2025-03-14', location: 'N/A', type: 'Alert', description: 'IOC hit on perimeter' },
  ],
  indicators: [
    { ioc: '192.0.2.100', type: 'IPv4', confidence: 0.92 },
    { ioc: 'malware-sample.exe', type: 'FileHash', confidence: 0.88 },
    { ioc: 'phishing-domain.tld', type: 'Domain', confidence: 0.95 },
    { ioc: 'user@relay.com', type: 'Email', confidence: 0.75 },
    { ioc: '198.51.100.50', type: 'IPv4', confidence: 0.85 },
    { ioc: 'a1b2c3d4e5f6...', type: 'FileHash', confidence: 0.91 },
    { ioc: 'c2-server.tld', type: 'Domain', confidence: 0.89 },
    { ioc: 'alert@phish.tld', type: 'Email', confidence: 0.72 },
  ],
};

/** People & photos: package 4. Table: name, phone, last_seen_location; expand row to show image. */
export const stubPeopleWithPhotosResults = {
  people: [
    { id: 'p1', name: 'Alex Chen', phone: '+1-555-201-1001', last_seen_location: 'Building A, Floor 3', image_url: 'https://picsum.photos/seed/p1/400/400' },
    { id: 'p2', name: 'Sam Rivera', phone: '+1-555-201-1002', last_seen_location: 'Cafeteria', image_url: 'https://picsum.photos/seed/p2/400/400' },
    { id: 'p3', name: 'Jordan Lee', phone: '+1-555-201-1003', last_seen_location: 'Conference Room B', image_url: 'https://picsum.photos/seed/p3/400/400' },
    { id: 'p4', name: 'Casey Morgan', phone: '+1-555-201-1004', last_seen_location: 'Main Office', image_url: 'https://picsum.photos/seed/p4/400/400' },
    { id: 'p5', name: 'Riley Taylor', phone: '+1-555-201-1005', last_seen_location: 'Lab 2', image_url: 'https://picsum.photos/seed/p5/400/400' },
    { id: 'p6', name: 'Quinn Adams', phone: '+1-555-201-1006', last_seen_location: 'Parking Lot', image_url: 'https://picsum.photos/seed/p6/400/400' },
  ],
  photos: [
    { id: 'img1', photo_id: 'p1', url: 'https://picsum.photos/seed/p1/400/400', caption: 'Alex Chen' },
    { id: 'img2', photo_id: 'p2', url: 'https://picsum.photos/seed/p2/400/400', caption: 'Sam Rivera' },
    { id: 'img3', photo_id: 'p3', url: 'https://picsum.photos/seed/p3/400/400', caption: 'Jordan Lee' },
    { id: 'img4', photo_id: 'p4', url: 'https://picsum.photos/seed/p4/400/400', caption: 'Casey Morgan' },
    { id: 'img5', photo_id: 'p5', url: 'https://picsum.photos/seed/p5/400/400', caption: 'Riley Taylor' },
    { id: 'img6', photo_id: 'p6', url: 'https://picsum.photos/seed/p6/400/400', caption: 'Quinn Adams' },
  ],
};

/** E-commerce package (5): orders, products, customers, reviews.
 *  Shared fields: product_id, product_name, customer_id, category. */
export const stubEcommerceResults = {
  orders_cube: [
    { id: 'ORD-001', customer_id: 'EC01', customer_name: 'Noa Levi',    product_id: 'P10', product_name: 'Wireless Earbuds',   category: 'Audio',    price: 89.90,  quantity: 1, order_date: '2025-01-05', status: 'delivered', payment: 'credit_card' },
    { id: 'ORD-002', customer_id: 'EC02', customer_name: 'Yosef Katz',  product_id: 'P11', product_name: 'USB-C Hub',          category: 'Accessories', price: 49.90, quantity: 2, order_date: '2025-01-08', status: 'delivered', payment: 'paypal' },
    { id: 'ORD-003', customer_id: 'EC03', customer_name: 'Tal Golan',   product_id: 'P12', product_name: 'Mechanical Keyboard', category: 'Input',    price: 159.00, quantity: 1, order_date: '2025-01-12', status: 'shipped', payment: 'credit_card' },
    { id: 'ORD-004', customer_id: 'EC01', customer_name: 'Noa Levi',    product_id: 'P13', product_name: 'Monitor Stand',       category: 'Accessories', price: 34.50, quantity: 1, order_date: '2025-01-15', status: 'delivered', payment: 'credit_card' },
    { id: 'ORD-005', customer_id: 'EC04', customer_name: 'Maya Cohen',  product_id: 'P10', product_name: 'Wireless Earbuds',   category: 'Audio',    price: 89.90,  quantity: 1, order_date: '2025-01-20', status: 'cancelled', payment: 'paypal' },
    { id: 'ORD-006', customer_id: 'EC05', customer_name: 'Avi Peretz',  product_id: 'P14', product_name: 'Webcam HD',           category: 'Video',    price: 74.00,  quantity: 1, order_date: '2025-02-01', status: 'delivered', payment: 'credit_card' },
    { id: 'ORD-007', customer_id: 'EC02', customer_name: 'Yosef Katz',  product_id: 'P12', product_name: 'Mechanical Keyboard', category: 'Input',    price: 159.00, quantity: 1, order_date: '2025-02-05', status: 'processing', payment: 'bit' },
    { id: 'ORD-008', customer_id: 'EC06', customer_name: 'Lior Ben-Ari', product_id: 'P15', product_name: 'Desk Lamp LED',      category: 'Lighting', price: 42.00,  quantity: 2, order_date: '2025-02-10', status: 'delivered', payment: 'paypal' },
    { id: 'ORD-009', customer_id: 'EC03', customer_name: 'Tal Golan',   product_id: 'P10', product_name: 'Wireless Earbuds',   category: 'Audio',    price: 89.90,  quantity: 1, order_date: '2025-02-14', status: 'shipped', payment: 'credit_card' },
    { id: 'ORD-010', customer_id: 'EC04', customer_name: 'Maya Cohen',  product_id: 'P15', product_name: 'Desk Lamp LED',      category: 'Lighting', price: 42.00,  quantity: 3, order_date: '2025-02-18', status: 'delivered', payment: 'bit' },
  ],
  ecom_products_cube: [
    { product_id: 'P10', product_name: 'Wireless Earbuds',   category: 'Audio',       brand: 'SoundMax',   unit_price: 89.90,  cost: 35.00, stock: 450,  rating: 4.6, reviews_count: 128 },
    { product_id: 'P11', product_name: 'USB-C Hub',          category: 'Accessories', brand: 'ConnectPro', unit_price: 49.90,  cost: 18.00, stock: 820,  rating: 4.3, reviews_count: 76 },
    { product_id: 'P12', product_name: 'Mechanical Keyboard', category: 'Input',      brand: 'KeyForce',   unit_price: 159.00, cost: 65.00, stock: 210,  rating: 4.8, reviews_count: 245 },
    { product_id: 'P13', product_name: 'Monitor Stand',       category: 'Accessories', brand: 'DeskFit',   unit_price: 34.50,  cost: 12.00, stock: 1100, rating: 4.1, reviews_count: 53 },
    { product_id: 'P14', product_name: 'Webcam HD',           category: 'Video',      brand: 'VisionPlus', unit_price: 74.00,  cost: 28.00, stock: 380,  rating: 4.4, reviews_count: 91 },
    { product_id: 'P15', product_name: 'Desk Lamp LED',       category: 'Lighting',   brand: 'LightUp',   unit_price: 42.00,  cost: 15.00, stock: 650,  rating: 4.2, reviews_count: 67 },
  ],
  ecom_customers_cube: [
    { customer_id: 'EC01', customer_name: 'Noa Levi',     email: 'noa@mail.com',    city: 'Tel Aviv',   total_orders: 5, total_spent: 412.30, member_since: '2023-02-15', tier: 'Gold' },
    { customer_id: 'EC02', customer_name: 'Yosef Katz',   email: 'yosef@mail.com',  city: 'Haifa',      total_orders: 3, total_spent: 258.80, member_since: '2023-07-10', tier: 'Silver' },
    { customer_id: 'EC03', customer_name: 'Tal Golan',    email: 'tal@mail.com',    city: 'Jerusalem',  total_orders: 4, total_spent: 497.90, member_since: '2022-11-22', tier: 'Gold' },
    { customer_id: 'EC04', customer_name: 'Maya Cohen',   email: 'maya@mail.com',   city: 'Netanya',    total_orders: 2, total_spent: 215.90, member_since: '2024-01-05', tier: 'Bronze' },
    { customer_id: 'EC05', customer_name: 'Avi Peretz',   email: 'avi@mail.com',    city: 'Beer Sheva', total_orders: 1, total_spent: 74.00,  member_since: '2024-06-18', tier: 'Bronze' },
    { customer_id: 'EC06', customer_name: 'Lior Ben-Ari', email: 'lior@mail.com',   city: 'Eilat',      total_orders: 2, total_spent: 126.00, member_since: '2024-03-30', tier: 'Silver' },
  ],
  reviews_cube: [
    { id: 'R01', product_id: 'P10', product_name: 'Wireless Earbuds',   customer_id: 'EC01', rating: 5, title: 'Amazing sound!',        date: '2025-01-10' },
    { id: 'R02', product_id: 'P11', product_name: 'USB-C Hub',          customer_id: 'EC02', rating: 4, title: 'Works great, compact',   date: '2025-01-12' },
    { id: 'R03', product_id: 'P12', product_name: 'Mechanical Keyboard', customer_id: 'EC03', rating: 5, title: 'Best keyboard ever',    date: '2025-01-18' },
    { id: 'R04', product_id: 'P13', product_name: 'Monitor Stand',       customer_id: 'EC01', rating: 3, title: 'Decent but wobbly',     date: '2025-01-20' },
    { id: 'R05', product_id: 'P14', product_name: 'Webcam HD',           customer_id: 'EC05', rating: 4, title: 'Clear picture quality',  date: '2025-02-05' },
    { id: 'R06', product_id: 'P15', product_name: 'Desk Lamp LED',       customer_id: 'EC06', rating: 5, title: 'Love the brightness',   date: '2025-02-12' },
    { id: 'R07', product_id: 'P10', product_name: 'Wireless Earbuds',   customer_id: 'EC03', rating: 4, title: 'Good but pricey',        date: '2025-02-16' },
    { id: 'R08', product_id: 'P12', product_name: 'Mechanical Keyboard', customer_id: 'EC02', rating: 5, title: 'Cherry MX rocks',       date: '2025-02-08' },
  ],
};

/** HR / Workforce package (6): employees, departments, attendance, payroll.
 *  Shared fields: employee_id, employee_name, department_id, department_name. */
export const stubHRResults = {
  employees_cube: [
    { employee_id: 'E001', employee_name: 'Shira Levy',   department_id: 'D01', department_name: 'Engineering', role: 'Senior Developer',  hire_date: '2021-03-15', salary: 22000, status: 'active',     manager_id: 'E010' },
    { employee_id: 'E002', employee_name: 'Oren Mizrahi', department_id: 'D01', department_name: 'Engineering', role: 'Junior Developer',  hire_date: '2023-08-01', salary: 14000, status: 'active',     manager_id: 'E001' },
    { employee_id: 'E003', employee_name: 'Dana Shapira', department_id: 'D02', department_name: 'Marketing',   role: 'Content Lead',      hire_date: '2022-01-10', salary: 16000, status: 'active',     manager_id: 'E010' },
    { employee_id: 'E004', employee_name: 'Amit Rosen',   department_id: 'D02', department_name: 'Marketing',   role: 'Designer',          hire_date: '2023-04-20', salary: 13000, status: 'active',     manager_id: 'E003' },
    { employee_id: 'E005', employee_name: 'Gal Dahan',    department_id: 'D03', department_name: 'Sales',       role: 'Account Executive', hire_date: '2022-06-05', salary: 15000, status: 'active',     manager_id: 'E010' },
    { employee_id: 'E006', employee_name: 'Rotem Avivi',  department_id: 'D03', department_name: 'Sales',       role: 'SDR',               hire_date: '2024-01-15', salary: 11000, status: 'active',     manager_id: 'E005' },
    { employee_id: 'E007', employee_name: 'Yael Barak',   department_id: 'D04', department_name: 'HR',          role: 'HR Manager',        hire_date: '2020-09-01', salary: 18000, status: 'active',     manager_id: 'E010' },
    { employee_id: 'E008', employee_name: 'Noam Gross',   department_id: 'D04', department_name: 'HR',          role: 'Recruiter',         hire_date: '2023-11-10', salary: 12000, status: 'active',     manager_id: 'E007' },
    { employee_id: 'E009', employee_name: 'Ido Friedman', department_id: 'D05', department_name: 'Finance',     role: 'Accountant',        hire_date: '2021-07-20', salary: 17000, status: 'on_leave',   manager_id: 'E010' },
    { employee_id: 'E010', employee_name: 'Tamar Gold',   department_id: 'D05', department_name: 'Finance',     role: 'CFO',               hire_date: '2019-01-05', salary: 32000, status: 'active',     manager_id: null },
  ],
  departments_cube: [
    { department_id: 'D01', department_name: 'Engineering', head: 'Shira Levy',   budget: 500000, headcount: 12, location: 'Tel Aviv',   floor: 3 },
    { department_id: 'D02', department_name: 'Marketing',   head: 'Dana Shapira', budget: 250000, headcount: 6,  location: 'Tel Aviv',   floor: 2 },
    { department_id: 'D03', department_name: 'Sales',       head: 'Gal Dahan',    budget: 350000, headcount: 8,  location: 'Haifa',      floor: 1 },
    { department_id: 'D04', department_name: 'HR',          head: 'Yael Barak',   budget: 150000, headcount: 4,  location: 'Tel Aviv',   floor: 2 },
    { department_id: 'D05', department_name: 'Finance',     head: 'Tamar Gold',   budget: 200000, headcount: 5,  location: 'Tel Aviv',   floor: 4 },
  ],
  attendance_cube: [
    { employee_id: 'E001', employee_name: 'Shira Levy',   department_id: 'D01', department_name: 'Engineering', date: '2025-03-10', check_in: '08:30', check_out: '17:45', hours: 9.25, type: 'office' },
    { employee_id: 'E002', employee_name: 'Oren Mizrahi', department_id: 'D01', department_name: 'Engineering', date: '2025-03-10', check_in: '09:00', check_out: '18:00', hours: 9.0,  type: 'office' },
    { employee_id: 'E003', employee_name: 'Dana Shapira', department_id: 'D02', department_name: 'Marketing',   date: '2025-03-10', check_in: '08:45', check_out: '16:30', hours: 7.75, type: 'remote' },
    { employee_id: 'E004', employee_name: 'Amit Rosen',   department_id: 'D02', department_name: 'Marketing',   date: '2025-03-10', check_in: '10:00', check_out: '18:30', hours: 8.5,  type: 'office' },
    { employee_id: 'E005', employee_name: 'Gal Dahan',    department_id: 'D03', department_name: 'Sales',       date: '2025-03-10', check_in: '07:45', check_out: '16:00', hours: 8.25, type: 'field' },
    { employee_id: 'E006', employee_name: 'Rotem Avivi',  department_id: 'D03', department_name: 'Sales',       date: '2025-03-10', check_in: '09:15', check_out: '17:30', hours: 8.25, type: 'office' },
    { employee_id: 'E007', employee_name: 'Yael Barak',   department_id: 'D04', department_name: 'HR',          date: '2025-03-10', check_in: '08:00', check_out: '17:00', hours: 9.0,  type: 'office' },
    { employee_id: 'E008', employee_name: 'Noam Gross',   department_id: 'D04', department_name: 'HR',          date: '2025-03-10', check_in: '09:30', check_out: '18:00', hours: 8.5,  type: 'remote' },
    { employee_id: 'E010', employee_name: 'Tamar Gold',   department_id: 'D05', department_name: 'Finance',     date: '2025-03-10', check_in: '08:00', check_out: '19:00', hours: 11.0, type: 'office' },
  ],
  payroll_cube: [
    { employee_id: 'E001', employee_name: 'Shira Levy',   department_id: 'D01', department_name: 'Engineering', month: '2025-02', gross: 22000, tax: 5720, pension: 1320, net: 14960 },
    { employee_id: 'E002', employee_name: 'Oren Mizrahi', department_id: 'D01', department_name: 'Engineering', month: '2025-02', gross: 14000, tax: 2800, pension: 840,  net: 10360 },
    { employee_id: 'E003', employee_name: 'Dana Shapira', department_id: 'D02', department_name: 'Marketing',   month: '2025-02', gross: 16000, tax: 3520, pension: 960,  net: 11520 },
    { employee_id: 'E004', employee_name: 'Amit Rosen',   department_id: 'D02', department_name: 'Marketing',   month: '2025-02', gross: 13000, tax: 2470, pension: 780,  net: 9750 },
    { employee_id: 'E005', employee_name: 'Gal Dahan',    department_id: 'D03', department_name: 'Sales',       month: '2025-02', gross: 15000, tax: 3150, pension: 900,  net: 10950 },
    { employee_id: 'E006', employee_name: 'Rotem Avivi',  department_id: 'D03', department_name: 'Sales',       month: '2025-02', gross: 11000, tax: 1870, pension: 660,  net: 8470 },
    { employee_id: 'E007', employee_name: 'Yael Barak',   department_id: 'D04', department_name: 'HR',          month: '2025-02', gross: 18000, tax: 4140, pension: 1080, net: 12780 },
    { employee_id: 'E008', employee_name: 'Noam Gross',   department_id: 'D04', department_name: 'HR',          month: '2025-02', gross: 12000, tax: 2160, pension: 720,  net: 9120 },
    { employee_id: 'E009', employee_name: 'Ido Friedman', department_id: 'D05', department_name: 'Finance',     month: '2025-02', gross: 17000, tax: 3740, pension: 1020, net: 12240 },
    { employee_id: 'E010', employee_name: 'Tamar Gold',   department_id: 'D05', department_name: 'Finance',     month: '2025-02', gross: 32000, tax: 9600, pension: 1920, net: 20480 },
  ],
};

/** Logistics / Shipping package (7): shipments, vehicles, warehouses, routes.
 *  Shared fields: warehouse_id, warehouse_name, vehicle_id, route_id, region. */
export const stubLogisticsResults = {
  shipments_cube: [
    { id: 'SHP-001', route_id: 'RT01', vehicle_id: 'V01', warehouse_id: 'W01', warehouse_name: 'Central Hub',    region: 'Center', origin: 'Tel Aviv',   destination: 'Haifa',      weight_kg: 320,  status: 'delivered',  ship_date: '2025-02-01', delivery_date: '2025-02-02' },
    { id: 'SHP-002', route_id: 'RT02', vehicle_id: 'V02', warehouse_id: 'W02', warehouse_name: 'Northern Depot', region: 'North',  origin: 'Haifa',      destination: 'Tiberias',   weight_kg: 150,  status: 'delivered',  ship_date: '2025-02-03', delivery_date: '2025-02-04' },
    { id: 'SHP-003', route_id: 'RT03', vehicle_id: 'V03', warehouse_id: 'W01', warehouse_name: 'Central Hub',    region: 'Center', origin: 'Tel Aviv',   destination: 'Beer Sheva', weight_kg: 500,  status: 'in_transit', ship_date: '2025-02-05', delivery_date: null },
    { id: 'SHP-004', route_id: 'RT01', vehicle_id: 'V04', warehouse_id: 'W03', warehouse_name: 'Southern Yard',  region: 'South',  origin: 'Beer Sheva', destination: 'Eilat',      weight_kg: 200,  status: 'delivered',  ship_date: '2025-02-06', delivery_date: '2025-02-08' },
    { id: 'SHP-005', route_id: 'RT04', vehicle_id: 'V01', warehouse_id: 'W01', warehouse_name: 'Central Hub',    region: 'Center', origin: 'Tel Aviv',   destination: 'Jerusalem',  weight_kg: 420,  status: 'delivered',  ship_date: '2025-02-10', delivery_date: '2025-02-11' },
    { id: 'SHP-006', route_id: 'RT02', vehicle_id: 'V05', warehouse_id: 'W02', warehouse_name: 'Northern Depot', region: 'North',  origin: 'Haifa',      destination: 'Nazareth',   weight_kg: 90,   status: 'delayed',    ship_date: '2025-02-12', delivery_date: null },
    { id: 'SHP-007', route_id: 'RT03', vehicle_id: 'V02', warehouse_id: 'W03', warehouse_name: 'Southern Yard',  region: 'South',  origin: 'Beer Sheva', destination: 'Ashdod',     weight_kg: 680,  status: 'delivered',  ship_date: '2025-02-14', delivery_date: '2025-02-15' },
    { id: 'SHP-008', route_id: 'RT04', vehicle_id: 'V03', warehouse_id: 'W01', warehouse_name: 'Central Hub',    region: 'Center', origin: 'Tel Aviv',   destination: 'Netanya',    weight_kg: 175,  status: 'in_transit', ship_date: '2025-02-18', delivery_date: null },
  ],
  vehicles_cube: [
    { vehicle_id: 'V01', plate: '12-345-67', type: 'Truck',      capacity_kg: 5000, region: 'Center', warehouse_id: 'W01', warehouse_name: 'Central Hub',    status: 'active',      mileage: 82000, fuel_type: 'diesel', last_service: '2025-01-15' },
    { vehicle_id: 'V02', plate: '23-456-78', type: 'Van',        capacity_kg: 1500, region: 'North',  warehouse_id: 'W02', warehouse_name: 'Northern Depot', status: 'active',      mileage: 54000, fuel_type: 'electric', last_service: '2025-02-01' },
    { vehicle_id: 'V03', plate: '34-567-89', type: 'Truck',      capacity_kg: 8000, region: 'Center', warehouse_id: 'W01', warehouse_name: 'Central Hub',    status: 'maintenance', mileage: 120000, fuel_type: 'diesel', last_service: '2025-02-20' },
    { vehicle_id: 'V04', plate: '45-678-90', type: 'Van',        capacity_kg: 1200, region: 'South',  warehouse_id: 'W03', warehouse_name: 'Southern Yard',  status: 'active',      mileage: 31000, fuel_type: 'electric', last_service: '2025-01-28' },
    { vehicle_id: 'V05', plate: '56-789-01', type: 'Motorcycle', capacity_kg: 50,   region: 'North',  warehouse_id: 'W02', warehouse_name: 'Northern Depot', status: 'active',      mileage: 15000, fuel_type: 'gasoline', last_service: '2025-02-10' },
  ],
  warehouses_cube: [
    { warehouse_id: 'W01', warehouse_name: 'Central Hub',    region: 'Center', city: 'Tel Aviv',   capacity_sqm: 5000, utilization: 0.78, employees: 35, temperature_control: true },
    { warehouse_id: 'W02', warehouse_name: 'Northern Depot', region: 'North',  city: 'Haifa',      capacity_sqm: 3000, utilization: 0.62, employees: 18, temperature_control: true },
    { warehouse_id: 'W03', warehouse_name: 'Southern Yard',  region: 'South',  city: 'Beer Sheva', capacity_sqm: 4000, utilization: 0.45, employees: 22, temperature_control: false },
  ],
  routes_cube: [
    { route_id: 'RT01', name: 'Central-North Express', region: 'Center', distance_km: 150, avg_duration_hrs: 2.5,  stops: 3, active: true, toll_cost: 25 },
    { route_id: 'RT02', name: 'Northern Circuit',      region: 'North',  distance_km: 90,  avg_duration_hrs: 1.5,  stops: 4, active: true, toll_cost: 15 },
    { route_id: 'RT03', name: 'South Corridor',        region: 'South',  distance_km: 280, avg_duration_hrs: 4.0,  stops: 5, active: true, toll_cost: 40 },
    { route_id: 'RT04', name: 'Jerusalem Line',        region: 'Center', distance_km: 65,  avg_duration_hrs: 1.25, stops: 2, active: true, toll_cost: 20 },
  ],
};

/** Stub lib descriptors for GET /api/libs (server-spec §3.1). */
export const stubLibs = [
  { id: 'lodash', name: 'Lodash', type: 'js', files: { js: 'lodash.js' } },
  { id: 'chart-js', name: 'Chart.js', type: 'js', files: { js: 'chart-js.js' } },
  { id: 'bootstrap', name: 'Bootstrap', type: 'js-css', files: { js: 'bootstrap.js', css: 'bootstrap.css' } },
  { id: 'normalize', name: 'Normalize.css', type: 'css', files: { css: 'normalize.css' } },
  { id: 'font-awesome', name: 'Font Awesome', type: 'js-css', files: { js: 'font-awesome.js', css: 'font-awesome.css' } },
  { id: 'leaflet', name: 'Leaflet', type: 'js-css', files: { js: 'leaflet.js', css: 'leaflet.css' } },
  {
    id: 'sqlite3-wasm',
    name: 'SQLite3 WASM',
    type: 'js-css',
    files: { js: 'sqlite3-wasm.js', css: 'sqlite3-wasm.css', wasm: 'sqlite3-wasm.wasm' },
  },
  {
    id: 'pyodide',
    name: 'Pyodide',
    type: 'js-css',
    files: { js: 'pyodide.js', css: 'pyodide.css', wasm: 'pyodide.wasm' },
  },
  {
    id: 'monaco-editor',
    name: 'Monaco Editor',
    type: 'js-css',
    files: { js: 'monaco-editor.js', css: 'monaco-editor.css', wasm: 'monaco-editor.wasm' },
  },
];

/** In-memory store for runId → snippet (mock Redis). 12h TTL not enforced in mock. */
const runStore = new Map();

/**
 * @param {string} runId
 * @param {{ htmlSnippet: string, librariesUsed: string[] }} value
 */
export const putRun = (runId, value) => {
  runStore.set(runId, value);
};

/**
 * @param {string} runId
 * @returns {{ htmlSnippet: string, librariesUsed: string[] } | undefined}
 */
export const getRun = (runId) => runStore.get(runId);
