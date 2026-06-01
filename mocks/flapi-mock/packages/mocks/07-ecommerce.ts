import { MockPackage, buildMetadata, quickParamsQuery } from '../package-base.js';

const data = {
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

export default new MockPackage({
  metadata: buildMetadata(7, 'E-commerce Analytics', data),
  quickParams: quickParamsQuery('ecom-query-1', [
    { name: 'category', defaultValues: ['Audio', 'Accessories', 'Input', 'Video', 'Lighting'] },
  ]),
  getResults: () => data,
});
