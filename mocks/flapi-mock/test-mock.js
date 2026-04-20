#!/usr/bin/env node
/**
 * Command-line test for mock server. Start server in another terminal or run against a running mock.
 * Usage: node test-mock.js [baseUrl]
 * Default baseUrl: http://localhost:6001
 */
const baseUrl = process.argv[2] || 'http://localhost:6001';
const AUTH_HEADER = { Authorization: 'Bearer mock-test-token' };

const parseBody = async (response) => {
  const text = await response.text();
  if (!text) return '';
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const get = (path) =>
  fetch(`${baseUrl}${path}`, { headers: AUTH_HEADER }).then(async (r) => ({
    status: r.status,
    body: parseBody(r),
  }));

const post = (path, body) =>
  fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...AUTH_HEADER },
    body: JSON.stringify(body),
  }).then(async (r) => ({
    status: r.status,
    body: parseBody(r),
  }));

const assert = (cond, msg) => {
  if (!cond) throw new Error(msg);
};

const run = async () => {
  // Health (no auth needed)
  const health = await get('/health');
  assert(health.status === 200, `GET /health expected 200, got ${health.status}`);
  const healthBody = await health.body;
  assert(healthBody?.ok === true, 'GET /health body.ok should be true');
  console.log('GET /health OK');

  // Search — by name
  const search = await get('/package/v1/search/Sales');
  assert(search.status === 200, `GET search expected 200, got ${search.status}`);
  const searchBody = await search.body;
  assert(Array.isArray(searchBody), 'search must return array');
  assert(searchBody.every((p) => p.Type === 'Package'), 'search must return only Type===Package');
  console.log('GET /package/v1/search/:partial OK');

  // Search — by ID (returns metadata with schema)
  const searchById = await get('/package/v1/search/7');
  assert(searchById.status === 200, `GET search by ID expected 200, got ${searchById.status}`);
  const searchByIdBody = await searchById.body;
  assert(Array.isArray(searchByIdBody) && searchByIdBody.length === 1, 'search by ID must return single-element array');
  assert(searchByIdBody[0].schema && typeof searchByIdBody[0].schema === 'object', 'search by ID must include schema');
  console.log('GET /package/v1/search/:id OK (includes schema)');

  // Run package
  const flapi = await post('/package/v3/7', {});
  assert(flapi.status === 200, `POST run expected 200, got ${flapi.status}`);
  const flapiBody = await flapi.body;
  assert(flapiBody?.results && typeof flapiBody.results === 'object', 'run body must have results');
  console.log('POST /package/v3/:id OK');

  // Run package — not found
  const notFoundPkg = await post('/package/v3/99999', {});
  assert(notFoundPkg.status === 404, `POST run unknown ID expected 404, got ${notFoundPkg.status}`);
  console.log('POST /package/v3/:id 404 for unknown ID OK');

  // Quick params info
  const quick = await get('/package/v1/quick/7');
  assert(quick.status === 200, `GET quick params expected 200, got ${quick.status}`);
  const quickBody = await quick.body;
  assert(quickBody && typeof quickBody === 'object', 'quick params must return object');
  console.log('GET /package/v1/quick/:id OK');

  // Run with quick params (package 20 — person by ID)
  const personRun = await post('/package/v3/20', { personId: { text: 2 } });
  assert(personRun.status === 200, `POST run with quick params expected 200, got ${personRun.status}`);
  const personBody = await personRun.body;
  assert(personBody?.results?.Person?.name === 'Noa T', `Expected person name 'Noa T', got ${personBody?.results?.Person?.name}`);
  console.log('POST /package/v3/20 with quick params OK');

  // Auth required
  const noAuth = await fetch(`${baseUrl}/package/v1/search/test`, { headers: {} });
  assert(noAuth.status === 401, `GET search without auth expected 401, got ${noAuth.status}`);
  console.log('GET /package/v1/search/:partial 401 without auth OK');

  console.log('\nAll mock tests passed.');
};

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
