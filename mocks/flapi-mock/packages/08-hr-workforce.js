import { MockPackage, tag, quickParamsQuery } from './package-base.js';

const data = {
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

export default new MockPackage({
  id: 8,
  name: 'HR & Workforce',
  tags: [tag('משאבי אנוש')],
  data,
  quickParams: quickParamsQuery('hr-query-1', 'HR Query', [
    { name: 'department', values: ['Engineering', 'Marketing', 'Sales', 'HR', 'Finance'] },
  ]),
});
