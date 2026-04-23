import { MockPackage } from './package-base.js';
import pkg01 from './mocks/01-sales.js';
import pkg03 from './mocks/03-intelligence.js';
import pkg04 from './mocks/04-people-photos.js';
import pkg05 from './mocks/05-realtime-dashboard.js';
import pkg06 from './mocks/06-people-hebrew.js';
import pkg07 from './mocks/07-ecommerce.js';
import pkg08 from './mocks/08-hr-workforce.js';
import pkg09 from './mocks/09-logistics.js';
import pkg10 from './mocks/10-phone-devices.js';
import pkg11 from './mocks/11-phone-calls.js';
import pkg12 from './mocks/12-phone-repairs.js';
import pkg13 from './mocks/13-phone-market.js';
import pkg14 from './mocks/14-required-param_with_default';
import pkg15 from './mocks/15-optional-params.js';
import pkg16 from './mocks/16-require-any.js';
import pkg17 from './mocks/17-mixed-params.js';
import pkg18 from './mocks/18-required-no-default.js';
import pkg20 from './mocks/20-person-by-id.js';
import pkg22 from './mocks/22-name-search.js';
import pkg23 from './mocks/23-person-by-name.js';

const allPackages: MockPackage[] = [
  pkg01,
  pkg03,
  pkg04,
  pkg05,
  pkg06,
  pkg07,
  pkg08,
  pkg09,
  pkg10,
  pkg11,
  pkg12,
  pkg13,
  pkg14,
  pkg15,
  pkg16,
  pkg17,
  pkg18,
  pkg20,
  pkg22,
  pkg23,
];

export const packageById = new Map(allPackages.map((pkg) => [String(pkg.id), pkg]));
