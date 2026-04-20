import { MockPackage, tag } from './package-base.js';

const data = {
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

export default new MockPackage({
  id: 9,
  name: 'Logistics & Shipping',
  tags: [tag('לוגיסטיקה')],
  data,
});
