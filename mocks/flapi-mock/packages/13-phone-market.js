import { MockPackage, tag } from './package-base.js';

const data = {
  market_share_cube: [
    { brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', units_sold: 52000, revenue_m: 51.9, market_share_pct: 35.2, yoy_growth: 4.1 },
    { brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', units_sold: 38000, revenue_m: 39.5, market_share_pct: 25.7, yoy_growth: 8.3 },
    { brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', units_sold: 12000, revenue_m: 11.9, market_share_pct: 8.1,  yoy_growth: 22.5 },
    { brand: 'OnePlus', category: 'Flagship', quarter: 'Q1-2025', units_sold: 8500,  revenue_m: 7.6,  market_share_pct: 5.8,  yoy_growth: 15.0 },
    { brand: 'Xiaomi',  category: 'Flagship', quarter: 'Q1-2025', units_sold: 15000, revenue_m: 13.5, market_share_pct: 10.2, yoy_growth: 12.8 },
    { brand: 'Apple',   category: 'Budget',   quarter: 'Q1-2025', units_sold: 28000, revenue_m: 12.0, market_share_pct: 18.9, yoy_growth: -2.5 },
    { brand: 'Samsung', category: 'Budget',   quarter: 'Q1-2025', units_sold: 45000, revenue_m: 17.1, market_share_pct: 30.5, yoy_growth: 6.7 },
    { brand: 'Xiaomi',  category: 'Budget',   quarter: 'Q1-2025', units_sold: 35000, revenue_m: 10.5, market_share_pct: 23.7, yoy_growth: 18.2 },
    { brand: 'Apple',   category: 'Flagship', quarter: 'Q4-2024', units_sold: 68000, revenue_m: 67.9, market_share_pct: 42.1, yoy_growth: 5.5 },
    { brand: 'Samsung', category: 'Flagship', quarter: 'Q4-2024', units_sold: 30000, revenue_m: 31.2, market_share_pct: 18.6, yoy_growth: 3.2 },
  ],
  sales_trends_cube: [
    { brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', month: '2025-01', units: 15000, avg_price: 998,  returns: 120, return_rate: 0.8 },
    { brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', month: '2025-02', units: 18000, avg_price: 995,  returns: 95,  return_rate: 0.5 },
    { brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', month: '2025-03', units: 19000, avg_price: 990,  returns: 110, return_rate: 0.6 },
    { brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', month: '2025-01', units: 14000, avg_price: 1050, returns: 180, return_rate: 1.3 },
    { brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', month: '2025-02', units: 12000, avg_price: 1020, returns: 140, return_rate: 1.2 },
    { brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', month: '2025-03', units: 12000, avg_price: 1010, returns: 130, return_rate: 1.1 },
    { brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', month: '2025-01', units: 3500,  avg_price: 950,  returns: 30,  return_rate: 0.9 },
    { brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', month: '2025-02', units: 4000,  avg_price: 920,  returns: 25,  return_rate: 0.6 },
    { brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', month: '2025-03', units: 4500,  avg_price: 899,  returns: 28,  return_rate: 0.6 },
  ],
  reviews_sentiment_cube: [
    { brand: 'Apple',   category: 'Flagship', model_name: 'iPhone 16 Pro',    device_id: 'PH01', quarter: 'Q1-2025', avg_rating: 4.6, reviews_total: 12500, positive_pct: 82, negative_pct: 8,  top_praise: 'Camera quality',  top_complaint: 'Price too high' },
    { brand: 'Apple',   category: 'Standard', model_name: 'iPhone 16',        device_id: 'PH02', quarter: 'Q1-2025', avg_rating: 4.4, reviews_total: 9800,  positive_pct: 78, negative_pct: 10, top_praise: 'Performance',     top_complaint: 'No ProMotion' },
    { brand: 'Samsung', category: 'Flagship', model_name: 'Galaxy S25 Ultra', device_id: 'PH03', quarter: 'Q1-2025', avg_rating: 4.5, reviews_total: 8200,  positive_pct: 80, negative_pct: 9,  top_praise: 'S Pen + AI',      top_complaint: 'Heavy weight' },
    { brand: 'Samsung', category: 'Standard', model_name: 'Galaxy S25',       device_id: 'PH04', quarter: 'Q1-2025', avg_rating: 4.3, reviews_total: 6100,  positive_pct: 76, negative_pct: 11, top_praise: 'Compact size',    top_complaint: 'Battery life' },
    { brand: 'Google',  category: 'Flagship', model_name: 'Pixel 9 Pro',      device_id: 'PH05', quarter: 'Q1-2025', avg_rating: 4.5, reviews_total: 4500,  positive_pct: 83, negative_pct: 7,  top_praise: 'AI features',     top_complaint: 'Availability' },
    { brand: 'OnePlus', category: 'Flagship', model_name: 'OnePlus 13',       device_id: 'PH07', quarter: 'Q1-2025', avg_rating: 4.4, reviews_total: 3200,  positive_pct: 79, negative_pct: 9,  top_praise: 'Fast charging',   top_complaint: 'Software bugs' },
    { brand: 'Xiaomi',  category: 'Flagship', model_name: 'Xiaomi 14 Ultra',  device_id: 'PH10', quarter: 'Q1-2025', avg_rating: 4.3, reviews_total: 2800,  positive_pct: 75, negative_pct: 12, top_praise: 'Leica camera',    top_complaint: 'MIUI ads' },
    { brand: 'Apple',   category: 'Budget',   model_name: 'iPhone SE 4',      device_id: 'PH08', quarter: 'Q1-2025', avg_rating: 4.2, reviews_total: 5600,  positive_pct: 74, negative_pct: 13, top_praise: 'Value for money', top_complaint: 'No always-on display' },
  ],
  carrier_data_cube: [
    { carrier: 'Cellcom',    brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', activations: 18000, avg_monthly_arpu: 89, churn_rate: 1.2, bundle_adoption: 45 },
    { carrier: 'Partner',    brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', activations: 15000, avg_monthly_arpu: 95, churn_rate: 0.9, bundle_adoption: 52 },
    { carrier: 'Hot Mobile', brand: 'Apple',   category: 'Flagship', quarter: 'Q1-2025', activations: 12000, avg_monthly_arpu: 85, churn_rate: 1.5, bundle_adoption: 38 },
    { carrier: 'Cellcom',    brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', activations: 14000, avg_monthly_arpu: 82, churn_rate: 1.4, bundle_adoption: 40 },
    { carrier: 'Partner',    brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', activations: 11000, avg_monthly_arpu: 88, churn_rate: 1.1, bundle_adoption: 48 },
    { carrier: 'Hot Mobile', brand: 'Samsung', category: 'Flagship', quarter: 'Q1-2025', activations: 9000,  avg_monthly_arpu: 79, churn_rate: 1.8, bundle_adoption: 35 },
    { carrier: 'Cellcom',    brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', activations: 4000,  avg_monthly_arpu: 92, churn_rate: 0.8, bundle_adoption: 55 },
    { carrier: 'Partner',    brand: 'Google',  category: 'Flagship', quarter: 'Q1-2025', activations: 3500,  avg_monthly_arpu: 90, churn_rate: 0.7, bundle_adoption: 60 },
  ],
};

export default new MockPackage({
  id: 13,
  name: 'Phone Market Analytics',
  tags: [tag('טלפונים'), tag('שוק')],
  data,
});
