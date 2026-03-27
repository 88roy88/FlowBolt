#!/usr/bin/env node
/**
 * Command-line test for mock server. Start server in another terminal or run against a running mock.
 * Usage: node test-mock.js [baseUrl]
 * Default baseUrl: http://localhost:6000
 */
const baseUrl = process.argv[2] || 'http://localhost:6000';

const parseBody = async (response) => {
  const text = await response.text();
  if (!text) return '';
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const get = (path) => fetch(`${baseUrl}${path}`).then(async (r) => ({ status: r.status, body: parseBody(r) }));
const post = (path, body) =>
  fetch(`${baseUrl}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(async (r) => ({
    status: r.status,
    body: parseBody(r),
  }));

const assert = (cond, msg) => {
  if (!cond) throw new Error(msg);
};

const run = async () => {
  const health = await get('/health');
  assert(health.status === 200, `GET /health expected 200, got ${health.status}`);
  const healthBody = await health.body;
  assert(healthBody?.ok === true, 'GET /health body.ok should be true');
  console.log('GET /health OK');

  const searchEmpty = await get('/api/flapi/packages/search');
  assert(searchEmpty.status === 422, `GET search without q expected 422, got ${searchEmpty.status}`);
  console.log('GET /api/flapi/packages/search 422 when q missing OK');

  const search = await get('/api/flapi/packages/search?q=Sales');
  assert(search.status === 200, `GET search expected 200, got ${search.status}`);
  const searchBody = await search.body;
  assert(Array.isArray(searchBody), 'search must return array');
  assert(searchBody.every((p) => p.Type === 'Package'), 'search must return only Type===Package');
  console.log('GET /api/flapi/packages/search OK');

  const flapi = await post('/api/flapi/packages/my-pkg/run', { param: 'value' });
  assert(flapi.status === 200, `POST flapi run expected 200, got ${flapi.status}`);
  const flapiBody = await flapi.body;
  assert(flapiBody?.results && typeof flapiBody.results === 'object', 'flapi body must have results');
  console.log('POST /api/flapi/packages/:id/run OK');

  const libs = await get('/api/libs');
  assert(libs.status === 200, `GET /api/libs expected 200, got ${libs.status}`);
  const libsBody = await libs.body;
  assert(Array.isArray(libsBody), 'GET /api/libs must return array');
  console.log('GET /api/libs OK');

  const gen = await post('/api/generate', {
    fieldExplanations: [{ fieldName: 'amount', explanation: 'USD' }],
    userPrompt: 'Bar chart',
    mainCubeName: 'sales_cube',
    mainCubeData: [{ region: 'North', amount: 100 }],
  });
  assert(gen.status === 200, `POST /api/generate expected 200, got ${gen.status}`);
  const genBody = await gen.body;
  assert(genBody?.runId && genBody?.htmlSnippet && Array.isArray(genBody?.librariesUsed), 'generate must return runId, htmlSnippet, librariesUsed');
  console.log('POST /api/generate OK');

  const feedback = await post('/api/feedback', { runId: genBody.runId, feedback: 'Make it blue' });
  assert(feedback.status === 200, `POST /api/feedback expected 200, got ${feedback.status}`);
  console.log('POST /api/feedback OK (valid runId)');

  const snippet = await get(`/api/snippets/${genBody.runId}.html`);
  assert(snippet.status === 200, `GET /api/snippets/:runId.html expected 200, got ${snippet.status}`);
  const snippetBody = await snippet.body;
  assert(typeof snippetBody === 'string' && snippetBody.includes('<html'), 'snippet must return html text');
  console.log('GET /api/snippets/:runId.html OK');

  const notFound = await post('/api/feedback', { runId: 'run_nonexistent', feedback: 'x' });
  assert(notFound.status === 404, `POST /api/feedback unknown runId expected 404, got ${notFound.status}`);
  console.log('POST /api/feedback 404 for unknown runId OK');

  console.log('All mock tests passed.');
};

run().catch((e) => {
  console.error(e);
  process.exit(1);
});
