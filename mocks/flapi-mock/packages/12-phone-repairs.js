import { MockPackage, tag } from './package-base.js';

const data = {
  repair_tickets_cube: [
    { ticket_id: 'TK001', device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', phone_number: '050-1234567', subscriber_name: 'Noa Levi',     technician_id: 'T01', issue: 'Cracked screen',      status: 'completed',    created: '2025-02-10', completed: '2025-02-12', cost: 850 },
    { ticket_id: 'TK002', device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', phone_number: '052-9876543', subscriber_name: 'Yosef Katz',   technician_id: 'T02', issue: 'Battery replacement',  status: 'completed',    created: '2025-02-15', completed: '2025-02-16', cost: 350 },
    { ticket_id: 'TK003', device_id: 'PH02', model_name: 'iPhone 16',        brand: 'Apple',   category: 'Standard', phone_number: '054-5551234', subscriber_name: 'Maya Cohen',   technician_id: 'T01', issue: 'Water damage',         status: 'in_progress',  created: '2025-03-01', completed: null, cost: null },
    { ticket_id: 'TK004', device_id: 'PH05', model_name: 'Pixel 9 Pro',      brand: 'Google',  category: 'Flagship', phone_number: '053-7771234', subscriber_name: 'Tal Golan',    technician_id: 'T03', issue: 'Camera not focusing',  status: 'completed',    created: '2025-02-20', completed: '2025-02-22', cost: 420 },
    { ticket_id: 'TK005', device_id: 'PH07', model_name: 'OnePlus 13',       brand: 'OnePlus', category: 'Flagship', phone_number: '055-3338888', subscriber_name: 'Avi Peretz',   technician_id: 'T02', issue: 'Charging port broken', status: 'waiting_parts', created: '2025-03-05', completed: null, cost: null },
    { ticket_id: 'TK006', device_id: 'PH04', model_name: 'Galaxy S25',       brand: 'Samsung', category: 'Standard', phone_number: '050-2225555', subscriber_name: 'Lior Ben-Ari', technician_id: 'T01', issue: 'Speaker malfunction',  status: 'completed',    created: '2025-03-08', completed: '2025-03-10', cost: 280 },
    { ticket_id: 'TK007', device_id: 'PH08', model_name: 'iPhone SE 4',      brand: 'Apple',   category: 'Budget',   phone_number: '052-4446666', subscriber_name: 'Dana Shapira', technician_id: 'T03', issue: 'Face ID not working',  status: 'in_progress',  created: '2025-03-12', completed: null, cost: null },
    { ticket_id: 'TK008', device_id: 'PH09', model_name: 'Galaxy A55',       brand: 'Samsung', category: 'Budget',   phone_number: '053-8889999', subscriber_name: 'Rotem Avivi', technician_id: 'T02', issue: 'Screen flickering',    status: 'completed',    created: '2025-03-14', completed: '2025-03-15', cost: 550 },
  ],
  parts_cube: [
    { part_id: 'PT01', device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', part_name: 'OLED Screen Assembly', category_part: 'Display', unit_cost: 320, stock: 15, supplier: 'Apple Parts IL',  lead_days: 3 },
    { part_id: 'PT02', device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', part_name: 'Battery 3582mAh',      category_part: 'Battery', unit_cost: 95,  stock: 30, supplier: 'Apple Parts IL',  lead_days: 2 },
    { part_id: 'PT03', device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', part_name: 'Battery 5000mAh',      category_part: 'Battery', unit_cost: 85,  stock: 25, supplier: 'Samsung Service', lead_days: 2 },
    { part_id: 'PT04', device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', part_name: 'AMOLED Screen',        category_part: 'Display', unit_cost: 450, stock: 8,  supplier: 'Samsung Service', lead_days: 5 },
    { part_id: 'PT05', device_id: 'PH05', model_name: 'Pixel 9 Pro',      brand: 'Google',  category: 'Flagship', part_name: 'Camera Module',        category_part: 'Camera',  unit_cost: 180, stock: 12, supplier: 'Global Parts Co', lead_days: 7 },
    { part_id: 'PT06', device_id: 'PH07', model_name: 'OnePlus 13',       brand: 'OnePlus', category: 'Flagship', part_name: 'USB-C Port Assembly',  category_part: 'Port',    unit_cost: 45,  stock: 0,  supplier: 'Global Parts Co', lead_days: 10 },
    { part_id: 'PT07', device_id: 'PH04', model_name: 'Galaxy S25',       brand: 'Samsung', category: 'Standard', part_name: 'Speaker Module',       category_part: 'Speaker', unit_cost: 55,  stock: 20, supplier: 'Samsung Service', lead_days: 3 },
    { part_id: 'PT08', device_id: 'PH09', model_name: 'Galaxy A55',       brand: 'Samsung', category: 'Budget',   part_name: 'LCD Screen',           category_part: 'Display', unit_cost: 180, stock: 18, supplier: 'Samsung Service', lead_days: 4 },
  ],
  technicians_cube: [
    { technician_id: 'T01', name: 'Dor Hadad',     specialization: 'Apple',   experience_years: 8,  certifications: 'Apple Certified',    tickets_completed: 342, avg_rating: 4.8, branch: 'Tel Aviv' },
    { technician_id: 'T02', name: 'Yonatan Segal', specialization: 'Android', experience_years: 5,  certifications: 'Samsung Certified',  tickets_completed: 215, avg_rating: 4.6, branch: 'Haifa' },
    { technician_id: 'T03', name: 'Miri Azulay',   specialization: 'All',     experience_years: 10, certifications: 'Apple + Samsung',     tickets_completed: 520, avg_rating: 4.9, branch: 'Tel Aviv' },
  ],
  warranty_cube: [
    { device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', phone_number: '050-1234567', subscriber_name: 'Noa Levi',     warranty_type: 'AppleCare+',       start_date: '2024-09-20', end_date: '2026-09-20', covers_accidental: true,  claims_used: 1 },
    { device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', phone_number: '052-9876543', subscriber_name: 'Yosef Katz',   warranty_type: 'Samsung Care',     start_date: '2025-01-22', end_date: '2027-01-22', covers_accidental: true,  claims_used: 1 },
    { device_id: 'PH02', model_name: 'iPhone 16',        brand: 'Apple',   category: 'Standard', phone_number: '054-5551234', subscriber_name: 'Maya Cohen',   warranty_type: 'Standard',         start_date: '2024-09-20', end_date: '2025-09-20', covers_accidental: false, claims_used: 0 },
    { device_id: 'PH05', model_name: 'Pixel 9 Pro',      brand: 'Google',  category: 'Flagship', phone_number: '053-7771234', subscriber_name: 'Tal Golan',    warranty_type: 'Google Preferred', start_date: '2024-08-22', end_date: '2026-08-22', covers_accidental: true,  claims_used: 1 },
    { device_id: 'PH07', model_name: 'OnePlus 13',       brand: 'OnePlus', category: 'Flagship', phone_number: '055-3338888', subscriber_name: 'Avi Peretz',   warranty_type: 'Standard',         start_date: '2025-01-07', end_date: '2026-01-07', covers_accidental: false, claims_used: 0 },
    { device_id: 'PH04', model_name: 'Galaxy S25',       brand: 'Samsung', category: 'Standard', phone_number: '050-2225555', subscriber_name: 'Lior Ben-Ari', warranty_type: 'Samsung Care',     start_date: '2025-01-22', end_date: '2027-01-22', covers_accidental: true,  claims_used: 1 },
  ],
};

export default new MockPackage({
  id: 12,
  name: 'Phone Repairs & Warranty',
  tags: [tag('טלפונים'), tag('תיקונים')],
  data,
});
