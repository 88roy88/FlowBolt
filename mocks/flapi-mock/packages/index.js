import pkg01 from './01-sales.js';
import pkg02 from './02-user-analytics.js';
import pkg03 from './03-intelligence.js';
import pkg04 from './04-people-photos.js';
import pkg05 from './05-realtime-dashboard.js';
import pkg06 from './06-people-hebrew.js';
import pkg07 from './07-ecommerce.js';
import pkg08 from './08-hr-workforce.js';
import pkg09 from './09-logistics.js';
import pkg10 from './10-phone-devices.js';
import pkg11 from './11-phone-calls.js';
import pkg12 from './12-phone-repairs.js';
import pkg13 from './13-phone-market.js';
import pkg20 from './20-person-by-id.js';

const allPackages = [pkg01, pkg02, pkg03, pkg04, pkg05, pkg06, pkg07, pkg08, pkg09, pkg10, pkg11, pkg12, pkg13, pkg20];

const packageById = new Map(allPackages.map((pkg) => [String(pkg.id), pkg]));

const searchablePackages = allPackages.map((pkg) => ({
  Id: pkg.id,
  Logo: '',
  Name: pkg.name,
  Type: 'Package',
}));

export function searchPackages(query) {
  const lowered = query.toLowerCase();
  return searchablePackages.filter((pkg) => pkg.Name.toLowerCase().includes(lowered));
}

/**
 * Get full metadata record for a package by numeric ID.
 * Used when the search query is a numeric ID (e.g. /package/v1/search/7).
 */
export function getPackageMetadata(id) {
  const numeric = Number(id);
  if (!Number.isFinite(numeric)) return null;

  const pkg = packageById.get(String(numeric));
  if (!pkg) return null;

  const base = {
    Purpose: '',
    Description: '',
    UserName: '',
    TimedPackageCount: 0,
    Tags: JSON.stringify([{ value: 'אפיון', label: 'אפיון' }]),
    Subjects: JSON.stringify([]),
  };

  return {
    Id: pkg.id,
    Name: pkg.name,
    ...base,
    Description: pkg.description || '',
    Tags: JSON.stringify(pkg.tags || []),
    schema: pkg.schema || {},
  };
}

/**
 * Quick params shape: { paramName: { SomeType: value }, ... }
 * Returns a flat { paramName: value } map, or null if body has no quick params.
 */
export function extractQuickParams(body) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  const extracted = {};
  for (const [paramName, paramObj] of Object.entries(body)) {
    if (paramObj && typeof paramObj === 'object' && !Array.isArray(paramObj)) {
      const values = Object.values(paramObj);
      extracted[paramName] = values.length === 1 ? values[0] : values;
    }
  }
  return Object.keys(extracted).length > 0 ? extracted : null;
}

/**
 * Run a package by ID, returning { results: {...} } or null if not found.
 */
export function getRunResults(dataSourceId, body) {
  const id = String(dataSourceId).trim();
  const pkg = packageById.get(id);
  if (!pkg) return null;
  return { results: pkg.getResults(body, extractQuickParams) };
}

/**
 * Get quick parameters info for a package by ID.
 */
export function getQuickParamsInfo(packageId) {
  const pkg = packageById.get(String(packageId).trim());
  return pkg?.quickParams || {};
}
