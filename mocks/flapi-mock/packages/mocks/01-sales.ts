import { MockPackage, buildMetadata } from '../package-base.js';

const data = {
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

export default new MockPackage({
  metadata: buildMetadata(1, 'Sample Sales Package', data),
  getResults: () => data,
});
