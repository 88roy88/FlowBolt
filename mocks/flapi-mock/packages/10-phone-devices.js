import { MockPackage, tag, quickParamsQuery } from './package-base.js';

const data = {
  devices_cube: [
    { device_id: 'PH01', model_name: 'iPhone 16 Pro',       brand: 'Apple',   category: 'Flagship', release_date: '2024-09-20', os: 'iOS 18',     color: 'Natural Titanium', storage_gb: 256, ram_gb: 8,  weight_g: 199, screen_size: 6.3 },
    { device_id: 'PH02', model_name: 'iPhone 16',           brand: 'Apple',   category: 'Standard', release_date: '2024-09-20', os: 'iOS 18',     color: 'Blue',             storage_gb: 128, ram_gb: 6,  weight_g: 170, screen_size: 6.1 },
    { device_id: 'PH03', model_name: 'Galaxy S25 Ultra',    brand: 'Samsung', category: 'Flagship', release_date: '2025-01-22', os: 'Android 15', color: 'Titanium Black',   storage_gb: 512, ram_gb: 12, weight_g: 218, screen_size: 6.9 },
    { device_id: 'PH04', model_name: 'Galaxy S25',          brand: 'Samsung', category: 'Standard', release_date: '2025-01-22', os: 'Android 15', color: 'Icy Blue',         storage_gb: 128, ram_gb: 8,  weight_g: 162, screen_size: 6.2 },
    { device_id: 'PH05', model_name: 'Pixel 9 Pro',         brand: 'Google',  category: 'Flagship', release_date: '2024-08-22', os: 'Android 14', color: 'Obsidian',         storage_gb: 256, ram_gb: 16, weight_g: 199, screen_size: 6.3 },
    { device_id: 'PH06', model_name: 'Pixel 9',             brand: 'Google',  category: 'Standard', release_date: '2024-08-22', os: 'Android 14', color: 'Wintergreen',      storage_gb: 128, ram_gb: 12, weight_g: 198, screen_size: 6.3 },
    { device_id: 'PH07', model_name: 'OnePlus 13',          brand: 'OnePlus', category: 'Flagship', release_date: '2025-01-07', os: 'Android 15', color: 'Midnight Ocean',   storage_gb: 256, ram_gb: 12, weight_g: 210, screen_size: 6.82 },
    { device_id: 'PH08', model_name: 'iPhone SE 4',         brand: 'Apple',   category: 'Budget',   release_date: '2025-03-01', os: 'iOS 18',     color: 'Starlight',        storage_gb: 128, ram_gb: 8,  weight_g: 163, screen_size: 6.1 },
    { device_id: 'PH09', model_name: 'Galaxy A55',          brand: 'Samsung', category: 'Budget',   release_date: '2024-03-11', os: 'Android 14', color: 'Awesome Navy',     storage_gb: 128, ram_gb: 8,  weight_g: 213, screen_size: 6.6 },
    { device_id: 'PH10', model_name: 'Xiaomi 14 Ultra',     brand: 'Xiaomi',  category: 'Flagship', release_date: '2024-02-22', os: 'Android 14', color: 'Black',            storage_gb: 512, ram_gb: 16, weight_g: 220, screen_size: 6.73 },
  ],
  specs_cube: [
    { device_id: 'PH01', model_name: 'iPhone 16 Pro',       brand: 'Apple',   category: 'Flagship', chip: 'A18 Pro',            battery_mah: 3582, camera_mp: 48,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 27 },
    { device_id: 'PH02', model_name: 'iPhone 16',           brand: 'Apple',   category: 'Standard', chip: 'A18',                battery_mah: 3561, camera_mp: 48,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 20 },
    { device_id: 'PH03', model_name: 'Galaxy S25 Ultra',    brand: 'Samsung', category: 'Flagship', chip: 'Snapdragon 8 Elite', battery_mah: 5000, camera_mp: 200, has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 45 },
    { device_id: 'PH04', model_name: 'Galaxy S25',          brand: 'Samsung', category: 'Standard', chip: 'Snapdragon 8 Elite', battery_mah: 4000, camera_mp: 50,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 25 },
    { device_id: 'PH05', model_name: 'Pixel 9 Pro',         brand: 'Google',  category: 'Flagship', chip: 'Tensor G4',          battery_mah: 4700, camera_mp: 50,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 27 },
    { device_id: 'PH06', model_name: 'Pixel 9',             brand: 'Google',  category: 'Standard', chip: 'Tensor G4',          battery_mah: 4700, camera_mp: 50,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 21 },
    { device_id: 'PH07', model_name: 'OnePlus 13',          brand: 'OnePlus', category: 'Flagship', chip: 'Snapdragon 8 Elite', battery_mah: 6000, camera_mp: 50,  has_5g: true, water_resistance: 'IP69', wireless_charging: true,  fast_charge_w: 100 },
    { device_id: 'PH08', model_name: 'iPhone SE 4',         brand: 'Apple',   category: 'Budget',   chip: 'A18',                battery_mah: 3279, camera_mp: 48,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 20 },
    { device_id: 'PH09', model_name: 'Galaxy A55',          brand: 'Samsung', category: 'Budget',   chip: 'Exynos 1480',        battery_mah: 5000, camera_mp: 50,  has_5g: true, water_resistance: 'IP67', wireless_charging: false, fast_charge_w: 25 },
    { device_id: 'PH10', model_name: 'Xiaomi 14 Ultra',     brand: 'Xiaomi',  category: 'Flagship', chip: 'Snapdragon 8 Gen 3', battery_mah: 5300, camera_mp: 50,  has_5g: true, water_resistance: 'IP68', wireless_charging: true,  fast_charge_w: 90 },
  ],
  subscribers_cube: [
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',     device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', carrier: 'Cellcom',    activation_date: '2024-10-01' },
    { phone_number: '052-9876543', subscriber_name: 'Yosef Katz',   device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', carrier: 'Partner',    activation_date: '2025-01-25' },
    { phone_number: '053-7771234', subscriber_name: 'Tal Golan',    device_id: 'PH05', model_name: 'Pixel 9 Pro',      brand: 'Google',  category: 'Flagship', carrier: 'Cellcom',    activation_date: '2024-09-01' },
    { phone_number: '054-5551234', subscriber_name: 'Maya Cohen',   device_id: 'PH02', model_name: 'iPhone 16',        brand: 'Apple',   category: 'Standard', carrier: 'Hot Mobile', activation_date: '2024-10-15' },
    { phone_number: '055-3338888', subscriber_name: 'Avi Peretz',   device_id: 'PH07', model_name: 'OnePlus 13',       brand: 'OnePlus', category: 'Flagship', carrier: 'Partner',    activation_date: '2025-01-10' },
    { phone_number: '050-2225555', subscriber_name: 'Lior Ben-Ari', device_id: 'PH04', model_name: 'Galaxy S25',       brand: 'Samsung', category: 'Standard', carrier: 'Hot Mobile', activation_date: '2025-02-01' },
    { phone_number: '052-4446666', subscriber_name: 'Dana Shapira', device_id: 'PH08', model_name: 'iPhone SE 4',      brand: 'Apple',   category: 'Budget',   carrier: 'Cellcom',    activation_date: '2025-03-05' },
    { phone_number: '053-8889999', subscriber_name: 'Rotem Avivi',  device_id: 'PH09', model_name: 'Galaxy A55',       brand: 'Samsung', category: 'Budget',   carrier: 'Partner',    activation_date: '2024-04-01' },
  ],
  pricing_cube: [
    { device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', base_price: 999,  current_price: 999,  discount_pct: 0,    in_stock: true,  retailer: 'iDigital' },
    { device_id: 'PH01', model_name: 'iPhone 16 Pro',    brand: 'Apple',   category: 'Flagship', base_price: 999,  current_price: 969,  discount_pct: 3,    in_stock: true,  retailer: 'KSP' },
    { device_id: 'PH02', model_name: 'iPhone 16',        brand: 'Apple',   category: 'Standard', base_price: 799,  current_price: 779,  discount_pct: 2.5,  in_stock: true,  retailer: 'iDigital' },
    { device_id: 'PH03', model_name: 'Galaxy S25 Ultra', brand: 'Samsung', category: 'Flagship', base_price: 1299, current_price: 1199, discount_pct: 7.7,  in_stock: true,  retailer: 'KSP' },
    { device_id: 'PH04', model_name: 'Galaxy S25',       brand: 'Samsung', category: 'Standard', base_price: 799,  current_price: 749,  discount_pct: 6.3,  in_stock: true,  retailer: 'Bug' },
    { device_id: 'PH05', model_name: 'Pixel 9 Pro',      brand: 'Google',  category: 'Flagship', base_price: 999,  current_price: 899,  discount_pct: 10,   in_stock: false, retailer: 'KSP' },
    { device_id: 'PH07', model_name: 'OnePlus 13',       brand: 'OnePlus', category: 'Flagship', base_price: 899,  current_price: 849,  discount_pct: 5.6,  in_stock: true,  retailer: 'KSP' },
    { device_id: 'PH08', model_name: 'iPhone SE 4',      brand: 'Apple',   category: 'Budget',   base_price: 429,  current_price: 429,  discount_pct: 0,    in_stock: true,  retailer: 'iDigital' },
    { device_id: 'PH09', model_name: 'Galaxy A55',       brand: 'Samsung', category: 'Budget',   base_price: 449,  current_price: 379,  discount_pct: 15.6, in_stock: true,  retailer: 'Bug' },
    { device_id: 'PH10', model_name: 'Xiaomi 14 Ultra',  brand: 'Xiaomi',  category: 'Flagship', base_price: 1099, current_price: 999,  discount_pct: 9.1,  in_stock: false, retailer: 'KSP' },
  ],
};

export default new MockPackage({
  id: 10,
  name: 'Phone Devices & Specs',
  tags: [tag('טלפונים')],
  data,
  quickParams: quickParamsQuery('phone-devices-query-1', 'Devices Query', [
    { name: 'brand', values: ['Apple', 'Samsung', 'Google', 'OnePlus', 'Xiaomi'] },
    { name: 'category', singleValue: true, values: ['Flagship', 'Standard', 'Budget'] },
  ]),
});
