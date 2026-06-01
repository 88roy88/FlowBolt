import { MockPackage, buildMetadata } from '../package-base.js';

const data = {
  calls_cube: [
    { id: 'CL001', phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    called_number: '052-9876543', direction: 'outgoing', duration_sec: 185, date: '2025-03-10', time: '08:32', type: 'voice', cost: 0 },
    { id: 'CL002', phone_number: '052-9876543', subscriber_name: 'Yosef Katz', device_id: 'PH03', carrier: 'Partner',    called_number: '050-1234567', direction: 'incoming', duration_sec: 185, date: '2025-03-10', time: '08:32', type: 'voice', cost: 0 },
    { id: 'CL003', phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    called_number: '054-5551234', direction: 'outgoing', duration_sec: 42,  date: '2025-03-10', time: '10:15', type: 'voice', cost: 0 },
    { id: 'CL004', phone_number: '053-7771234', subscriber_name: 'Tal Golan',  device_id: 'PH05', carrier: 'Cellcom',    called_number: '1-800-123456', direction: 'outgoing', duration_sec: 320, date: '2025-03-10', time: '11:00', type: 'voice', cost: 0 },
    { id: 'CL005', phone_number: '054-5551234', subscriber_name: 'Maya Cohen', device_id: 'PH02', carrier: 'Hot Mobile', called_number: '+44-20-1234',  direction: 'outgoing', duration_sec: 95,  date: '2025-03-11', time: '09:45', type: 'international', cost: 4.50 },
    { id: 'CL006', phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    called_number: '052-9876543', direction: 'outgoing', duration_sec: 0,   date: '2025-03-11', time: '14:20', type: 'missed', cost: 0 },
    { id: 'CL007', phone_number: '055-3338888', subscriber_name: 'Avi Peretz', device_id: 'PH07', carrier: 'Partner',    called_number: '050-1234567', direction: 'outgoing', duration_sec: 540, date: '2025-03-12', time: '16:00', type: 'voice', cost: 0 },
    { id: 'CL008', phone_number: '052-9876543', subscriber_name: 'Yosef Katz', device_id: 'PH03', carrier: 'Partner',    called_number: '+1-212-5550123', direction: 'outgoing', duration_sec: 180, date: '2025-03-12', time: '20:00', type: 'international', cost: 6.00 },
    { id: 'CL009', phone_number: '053-7771234', subscriber_name: 'Tal Golan',  device_id: 'PH05', carrier: 'Cellcom',    called_number: '054-5551234', direction: 'outgoing', duration_sec: 75,  date: '2025-03-13', time: '07:30', type: 'voice', cost: 0 },
    { id: 'CL010', phone_number: '054-5551234', subscriber_name: 'Maya Cohen', device_id: 'PH02', carrier: 'Hot Mobile', called_number: '053-7771234', direction: 'incoming', duration_sec: 75,  date: '2025-03-13', time: '07:30', type: 'voice', cost: 0 },
    { id: 'CL011', phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    called_number: '055-3338888', direction: 'incoming', duration_sec: 260, date: '2025-03-13', time: '12:00', type: 'voice', cost: 0 },
    { id: 'CL012', phone_number: '055-3338888', subscriber_name: 'Avi Peretz', device_id: 'PH07', carrier: 'Partner',    called_number: '*100',        direction: 'outgoing', duration_sec: 120, date: '2025-03-14', time: '09:00', type: 'service', cost: 0 },
  ],
  contacts_cube: [
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    contact_name: 'Yosef Katz',  contact_number: '052-9876543', relationship: 'friend',   call_count: 28, last_call: '2025-03-11' },
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    contact_name: 'Maya Cohen',  contact_number: '054-5551234', relationship: 'colleague', call_count: 12, last_call: '2025-03-10' },
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    contact_name: 'Avi Peretz',  contact_number: '055-3338888', relationship: 'family',    call_count: 45, last_call: '2025-03-13' },
    { phone_number: '052-9876543', subscriber_name: 'Yosef Katz', device_id: 'PH03', carrier: 'Partner',    contact_name: 'Noa Levi',    contact_number: '050-1234567', relationship: 'friend',   call_count: 28, last_call: '2025-03-10' },
    { phone_number: '053-7771234', subscriber_name: 'Tal Golan',  device_id: 'PH05', carrier: 'Cellcom',    contact_name: 'Maya Cohen',  contact_number: '054-5551234', relationship: 'colleague', call_count: 15, last_call: '2025-03-13' },
    { phone_number: '054-5551234', subscriber_name: 'Maya Cohen', device_id: 'PH02', carrier: 'Hot Mobile', contact_name: 'Tal Golan',   contact_number: '053-7771234', relationship: 'colleague', call_count: 15, last_call: '2025-03-13' },
    { phone_number: '055-3338888', subscriber_name: 'Avi Peretz', device_id: 'PH07', carrier: 'Partner',    contact_name: 'Noa Levi',    contact_number: '050-1234567', relationship: 'family',    call_count: 45, last_call: '2025-03-13' },
  ],
  usage_summary_cube: [
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    month: '2025-03', voice_minutes: 320, sms_count: 85,  data_gb: 12.4, intl_minutes: 0,  total_cost: 59.90 },
    { phone_number: '052-9876543', subscriber_name: 'Yosef Katz', device_id: 'PH03', carrier: 'Partner',    month: '2025-03', voice_minutes: 180, sms_count: 40,  data_gb: 8.2,  intl_minutes: 15, total_cost: 79.90 },
    { phone_number: '053-7771234', subscriber_name: 'Tal Golan',  device_id: 'PH05', carrier: 'Cellcom',    month: '2025-03', voice_minutes: 450, sms_count: 120, data_gb: 18.7, intl_minutes: 0,  total_cost: 59.90 },
    { phone_number: '054-5551234', subscriber_name: 'Maya Cohen', device_id: 'PH02', carrier: 'Hot Mobile', month: '2025-03', voice_minutes: 95,  sms_count: 200, data_gb: 25.3, intl_minutes: 8,  total_cost: 99.90 },
    { phone_number: '055-3338888', subscriber_name: 'Avi Peretz', device_id: 'PH07', carrier: 'Partner',    month: '2025-03', voice_minutes: 600, sms_count: 30,  data_gb: 5.1,  intl_minutes: 0,  total_cost: 69.90 },
    { phone_number: '050-1234567', subscriber_name: 'Noa Levi',   device_id: 'PH01', carrier: 'Cellcom',    month: '2025-02', voice_minutes: 290, sms_count: 78,  data_gb: 10.8, intl_minutes: 0,  total_cost: 59.90 },
    { phone_number: '052-9876543', subscriber_name: 'Yosef Katz', device_id: 'PH03', carrier: 'Partner',    month: '2025-02', voice_minutes: 210, sms_count: 55,  data_gb: 9.5,  intl_minutes: 22, total_cost: 89.90 },
  ],
  plans_cube: [
    { plan_id: 'PLN01', plan_name: 'Basic 60',     carrier: 'Cellcom',    monthly_cost: 59.90,  voice_minutes: 'unlimited', sms: 'unlimited', data_gb: 30,  intl_minutes: 0,  includes_5g: false },
    { plan_id: 'PLN02', plan_name: 'Premium 80',    carrier: 'Partner',    monthly_cost: 79.90,  voice_minutes: 'unlimited', sms: 'unlimited', data_gb: 50,  intl_minutes: 30, includes_5g: true },
    { plan_id: 'PLN03', plan_name: 'Unlimited Max', carrier: 'Hot Mobile', monthly_cost: 99.90,  voice_minutes: 'unlimited', sms: 'unlimited', data_gb: 100, intl_minutes: 60, includes_5g: true },
  ],
};

export default new MockPackage({
  metadata: buildMetadata(11, 'Phone Call Records', data),
  getResults: () => data,
});
