import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { errorBody } from './errorBody.js';
import {
  stubDataSourceResults,
  stubIntelligenceResults,
  stubPeopleWithPhotosResults,
  stubPeopleHebrewResults,
  stubLibs,
  putRun,
  getRun,
  getRealtimeMetrics,
  stubHRResults,
  stubEcommerceResults,
  stubLogisticsResults,
  stubPhoneDevicesResults,
  stubPhoneCallsResults,
  stubPhoneRepairsResults,
  stubPhoneMarketResults,
  getPersonById
} from './stubData.js';

const app = express();
app.use(cors());
// Allow any valid JSON (including primitives), because Swagger/UI often defaults to `"string"`.
app.use(express.json({ limit: '10mb', strict: false }));

const PORT = Number(process.env.MOCK_PORT) || 6001;
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;
const IFRAME_DATA_EVENT = process.env.IFRAME_DATA_EVENT || 'IFRAME_DATA';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const libsRoot =
  process.env.LIBS_ROOT || path.join(__dirname, '..', 'libs');
app.use('/libs', express.static(libsRoot));

// Serve static files from public directory (mock SSO page, etc.)
const publicRoot = path.join(__dirname, 'public');
app.use(express.static(publicRoot));

/** Minimal stub for flapi package search autocomplete. Server-spec §2.1: filter to Type === "Package". */
const stubSearchResultsRaw = [
  { Id: 1, Logo: '', Name: 'Sample Sales Package', Type: 'Package' },
  { Id: 2, Logo: '', Name: 'User Analytics Package', Type: 'Package' },
  { Id: 3, Logo: '', Name: 'Intelligence Briefing', Type: 'Package' },
  { Id: 4, Logo: '', Name: 'People & Photos', Type: 'Package' },
  { Id: 5, Logo: '', Name: 'Real-Time Server Dashboard', Type: 'Package' },
  { Id: 6, Logo: '', Name: 'People Hebrew Names', Type: 'Package' },
  { Id: 7, Logo: '', Name: 'E-commerce Analytics', Type: 'Package' },
  { Id: 8, Logo: '', Name: 'HR & Workforce', Type: 'Package' },
  { Id: 9, Logo: '', Name: 'Logistics & Shipping', Type: 'Package' },
  { Id: 10, Logo: '', Name: 'Phone Devices & Specs', Type: 'Package' },
  { Id: 11, Logo: '', Name: 'Phone Call Records', Type: 'Package' },
  { Id: 12, Logo: '', Name: 'Phone Repairs & Warranty', Type: 'Package' },
  { Id: 13, Logo: '', Name: 'Phone Market Analytics', Type: 'Package' },
  { Id: 99, Logo: '', Name: 'Internal Template', Type: 'Template' },
];
const PACKAGE_TYPE = 'Package';

/** Library injection config matching server-spec §5 (mocked mapping). */
const libraryInjectionConfigs = [
  {
    id: 'chart-js',
    placeholder: '<Library:ChartJS />',
    location: 'head',
  },
  {
    id: 'leaflet',
    placeholder: '<Library:Leaflet />',
    location: 'head',
  },
  {
    id: 'sqlite3-wasm',
    placeholder: '<Library:Sqlite3Wasm />',
    location: 'head',
  },
  {
    id: 'pyodide',
    placeholder: '<Library:Pyodide />',
    location: 'head',
  },
  {
    id: 'monaco-editor',
    placeholder: '<Library:MonacoEditor />',
    location: 'head',
  },
];

const findLibById = (id) => stubLibs.find((lib) => lib.id === id);

const buildLibraryTags = (libId) => {
  const lib = findLibById(libId);
  if (!lib) {
    return { tags: '', used: false };
  }

  const parts = [];
  const prefix = `${BASE_URL}/libs/`;

  if (lib.type === 'js' || lib.type === 'js-css') {
    const jsFile = lib.files?.js;
    if (jsFile) {
      parts.push(`<script src="${prefix}${jsFile}"></script>`);
    }
  }

  if (lib.type === 'css' || lib.type === 'js-css') {
    const cssFile = lib.files?.css;
    if (cssFile) {
      parts.push(`<link rel="stylesheet" href="${prefix}${cssFile}" />`);
    }
  }

  return { tags: parts.join(''), used: parts.length > 0 };
};

const injectLibraries = (rawHtml) => {
  let html = rawHtml;
  const usedLibIds = new Set();

  libraryInjectionConfigs.forEach((cfg) => {
    if (!html.includes(cfg.placeholder)) {
      return;
    }

    html = html.replace(cfg.placeholder, '');
    const { tags, used } = buildLibraryTags(cfg.id);
    if (!used || !tags) {
      return;
    }

    if (cfg.location === 'head') {
      if (html.includes('</head>')) {
        html = html.replace('</head>', `${tags}</head>`);
      } else {
        html = html.replace('<body', `${tags}<body`);
      }
    } else {
      if (html.includes('</body>')) {
        html = html.replace('</body>', `${tags}</body>`);
      } else {
        html = `${html}${tags}`;
      }
    }

    usedLibIds.add(cfg.id);
  });

  return { html, librariesUsed: Array.from(usedLibIds) };
};

const injectDataListener = (html) => {
  const sentinel = '__DATA_INJECTION_SENTINEL__';
  if (html.includes(sentinel)) {
    return html;
  }

  const script = `<script>${sentinel};(function(){const eventName=${JSON.stringify(
    IFRAME_DATA_EVENT,
  )};window.data=null;window.addEventListener("message",function(event){const message=event.data;if(!message||message.type!==eventName){return;}window.data=message.payload;});})();</script>`;

  if (html.includes('</body>')) {
    return html.replace('</body>', `${script}</body>`);
  }
  return `${html}${script}`;
};

const applyInjectionFlows = (rawHtml) => {
  const { html: withLibs, librariesUsed } = injectLibraries(rawHtml);
  const withData = injectDataListener(withLibs);
  return { htmlSnippet: withData, librariesUsed };
};

/** FLAPI expects a non-empty Authorization header; empty or missing => 401 (mock parity). */
const assertFlapiApiAuthorized = (req, res) => {
  const raw = req.headers.authorization;
  if (typeof raw !== 'string' || !raw.trim()) {
    res
      .status(401)
      .json(errorBody('unauthorized', 'Authorization header is required'));
    return false;
  }
  return true;
};

const buildMockModelPromptText = (body) => {
  const userPrompt =
    typeof body?.userPrompt === 'string' ? body.userPrompt.trim() : '';
  const systemPrompt =
    typeof body?.systemPrompt === 'string' ? body.systemPrompt.trim() : '';
  const structuredOutputPrompt =
    typeof body?.structuredOutputPrompt === 'string'
      ? body.structuredOutputPrompt.trim()
      : '';
  const restrictionsPrompt =
    typeof body?.restrictionsPrompt === 'string'
      ? body.restrictionsPrompt.trim()
      : '';

  return JSON.stringify(
    {
      mock: true,
      userPrompt,
      systemPrompt,
      structuredOutputPrompt,
      restrictionsPrompt,
    },
    null,
    2,
  );
};

// ——— 2. Flapi proxy (mock) ———
// Real Server proxies to FLAPI_URL/package/v1/search/{q} and FLAPI_URL/package/{id}, so mock must expose those too
function handlePackageSearch(query) {
  const q = (query || '').trim();
  if (!q) {
    return { status: 422, body: errorBody('validation_failed', 'Query parameter "q" is required') };
  }
  const lowered = q.toLowerCase();
  const nameMatch = (pkg) => pkg.Name.toLowerCase().includes(lowered);
  const packagesOnly = stubSearchResultsRaw.filter((pkg) => pkg.Type === PACKAGE_TYPE);
  const filtered = packagesOnly.filter(nameMatch);
  return { status: 200, body: filtered };
}

function buildPackageSearchRecordById(id) {
  const trimmed = String(id ?? '').trim();
  if (!trimmed) return null;

  // Real FLAPI returns 200 with [] when not found.
  // We stub a small set of known package IDs that are useful in development.
  const base = {
    Purpose: '',
    Description: '',
    UserName: '',
    TimedPackageCount: 0,
    Tags: JSON.stringify([{ value: 'אפיון', label: 'אפיון' }]),
    Subjects: JSON.stringify([]),
  };

  const known = {
    1: { Id: 1, Name: 'Sample Sales Package', ...base },
    2: { Id: 2, Name: 'User Analytics Package', ...base },
    3: { Id: 3, Name: 'Intelligence Briefing', ...base, Tags: JSON.stringify([{ value: 'מודיעין', label: 'מודיעין' }]) },
    4: { Id: 4, Name: 'People & Photos', ...base, Tags: JSON.stringify([{ value: 'אנשים', label: 'אנשים' }]) },
    5: { Id: 5, Name: 'Real-Time Server Dashboard', ...base, Tags: JSON.stringify([{ value: 'real-time', label: 'real-time' }, { value: 'monitoring', label: 'monitoring' }]) },
    6: { Id: 6, Name: 'People Hebrew Names', ...base, Description: 'Hebrew names for people (same IDs as People & Photos)', Tags: JSON.stringify([{ value: 'אנשים', label: 'אנשים' }, { value: 'עברית', label: 'עברית' }]) },
    7: { Id: 7, Name: 'E-commerce Analytics', ...base, Tags: JSON.stringify([{ value: 'אי-קומרס', label: 'אי-קומרס' }]) },
    8: { Id: 8, Name: 'HR & Workforce', ...base, Tags: JSON.stringify([{ value: 'משאבי אנוש', label: 'משאבי אנוש' }]) },
    9: { Id: 9, Name: 'Logistics & Shipping', ...base, Tags: JSON.stringify([{ value: 'לוגיסטיקה', label: 'לוגיסטיקה' }]) },
    10: { Id: 10, Name: 'Phone Devices & Specs', ...base, Tags: JSON.stringify([{ value: 'טלפונים', label: 'טלפונים' }]) },
    11: { Id: 11, Name: 'Phone Call Records', ...base, Tags: JSON.stringify([{ value: 'טלפונים', label: 'טלפונים' }, { value: 'שיחות', label: 'שיחות' }]) },
    12: { Id: 12, Name: 'Phone Repairs & Warranty', ...base, Tags: JSON.stringify([{ value: 'טלפונים', label: 'טלפונים' }, { value: 'תיקונים', label: 'תיקונים' }]) },
    13: { Id: 13, Name: 'Phone Market Analytics', ...base, Tags: JSON.stringify([{ value: 'טלפונים', label: 'טלפונים' }, { value: 'שוק', label: 'שוק' }]) },
    20: { Id: 20, Name: 'Get Person by ID', ...base, Tags: JSON.stringify([{ value: 'דוגמה', label: 'דוגמה' }]) },
    572903: { Id: 572903, Name: 'כרטסת - base', ...base },
  };

  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return null;
  return known[numeric] ?? null;
}

function handlePackageSearchByPartialOrId(partialOrId) {
  const q = String(partialOrId ?? '').trim();
  if (!q) {
    return { status: 422, body: errorBody('validation_failed', 'Query parameter "q" is required') };
  }

  // If caller passes numeric ID (e.g. /package/v1/search/572903) return package metadata array.
  if (/^\d+$/.test(q)) {
    const record = buildPackageSearchRecordById(q);
    return { status: 200, body: record ? [record] : [] };
  }

  // Otherwise behave like autocomplete by name.
  return handlePackageSearch(q);
}

app.get('/package/v1/search/:partial', (req, res) => {
  if (!assertFlapiApiAuthorized(req, res)) return;
  const { status, body } = handlePackageSearchByPartialOrId(req.params.partial);
  res.status(status).json(body);
});

app.get('/api/flapi/packages/search', (req, res) => {
  if (!assertFlapiApiAuthorized(req, res)) return;
  const query = typeof req.query.q === 'string' ? req.query.q : '';
  const { status, body } = handlePackageSearchByPartialOrId(query);
  res.status(status).json(body);
});

function extractQuickParams(body) {
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

function getRunResults(dataSourceId, body) {
  const id = String(dataSourceId).trim();
  switch (id) {
    case '3':
        return { results: { ...stubIntelligenceResults } };
    case '4':
        return { results: { ...stubPeopleWithPhotosResults } };
    case '5':
        return { results: getRealtimeMetrics() };
    case '6':
        return { results: { ...stubPeopleHebrewResults } };
    case '7':
        return { results: { ...stubEcommerceResults } };
    case '8':
        return { results: { ...stubHRResults } };
    case '9':
        return { results: { ...stubLogisticsResults } };
    case '10':
        return { results: { ...stubPhoneDevicesResults } };
    case '11':
        return { results: { ...stubPhoneCallsResults } };
    case '12':
        return { results: { ...stubPhoneRepairsResults } };
    case '13':
        return { results: { ...stubPhoneMarketResults } };
    case '20':
        // Example of using quick params from request body to modify results.
        const quickParams = extractQuickParams(body);
        const personId = quickParams?.personId;
        const person = getPersonById(personId);
        return { results: person ? { Person: person } : null };
      default:
        return null;

  }
}

function runPackageById(req, res) {
    if (!assertFlapiApiAuthorized(req, res)){
      return res.status(401).json(errorBody('unauthorized', 'Authorization header is required'));
    }
    const dataSourceId = req.params.packageId;
    if (!dataSourceId?.trim()) {
      return res.status(400).json(errorBody('invalid_data_source_id', 'dataSourceId is required'));
    }
    let results = getRunResults(dataSourceId, req.body);
    if (results) {
      return res.status(200).json(results);
    } else {
      return res.status(404).json(errorBody('not_found', `No package found for id: ${dataSourceId}`));
    }
}

app.post('/package/:packageId', (req, res) => {
  return runPackageById(req, res);
});

app.post('/package/v3/:packageId', (req, res) => {
  return runPackageById(req, res);
});

app.post('/api/flapi/packages/:packageId/run', (req, res) => {
  return runPackageById(req, res);
});

app.post('/api/flapi/package/v3/:packageId', (req, res) => {
  return runPackageById(req, res);
});

// ——— Config & Models (for client) ———
app.get('/api/config', (_req, res) => {
  res.status(200).json({
    baseUrl: BASE_URL,
    iframeDataEvent: IFRAME_DATA_EVENT,
  });
});

app.get('/api/models', (_req, res) => {
  res.status(200).json([
    { id: 'default', name: 'Default (mock)', provider: 'local' },
    { id: 'minimax', name: 'MiniMax', provider: 'MiniMax' },
  ]);
});

// ——— 3. Libs ———
app.get('/api/libs', (_req, res) => {
  res.status(200).json(stubLibs);
});

// ——— 4. Agent (generate) ———
app.post('/api/generate', (req, res) => {
  const body = req.body;
  const fieldExplanations = body?.fieldExplanations;
  const userPrompt = body?.userPrompt;
  const mainCubeName = body?.mainCubeName;
  const mainCubeData = body?.mainCubeData;

  if (!Array.isArray(fieldExplanations) || fieldExplanations.length > 16) {
    return res
      .status(422)
      .json(
        errorBody(
          'validation_failed',
          'fieldExplanations must be an array with up to 16 items',
        ),
      );
  }
  if (typeof userPrompt !== 'string' || !userPrompt.trim()) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'userPrompt is required'));
  }
  if (typeof mainCubeName !== 'string' || !mainCubeName.trim()) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'mainCubeName is required'));
  }
  if (!Array.isArray(mainCubeData)) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'mainCubeData must be an array'));
  }

  const runId = `run_${Date.now()}_${Math.random()
    .toString(36)
    .slice(2, 9)}`;

  const rawHtml = [
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '<title>Stub snippet</title>',
    '<Library:ChartJS />',
    '</head>',
    '<body>',
    `<div id="app">Generated stub. Data rows: ${mainCubeData.length}. Prompt: ${userPrompt
      .trim()
      .slice(0, 80)}</div>`,
    '</body>',
    '</html>',
  ].join('');

  const { htmlSnippet, librariesUsed } = applyInjectionFlows(rawHtml);
  putRun(runId, { htmlSnippet, librariesUsed });
  res.status(200).json({ runId, htmlSnippet, librariesUsed });
});

// ——— 4.2 Feedback ———
app.post('/api/feedback', (req, res) => {
  const { runId, feedback } = req.body ?? {};
  if (typeof runId !== 'string' || !runId.trim()) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'runId is required'));
  }
  if (typeof feedback !== 'string' || !feedback.trim()) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'feedback is required'));
  }

  const existing = getRun(runId);
  if (!existing) {
    return res
      .status(404)
      .json(errorBody('run_not_found', `No run found for runId: ${runId}`));
  }

  const rawHtml = [
    '<!DOCTYPE html>',
    '<html>',
    '<head>',
    '<title>Stub snippet (feedback)</title>',
    '<Library:ChartJS />',
    '</head>',
    '<body>',
    `<div id="app">Updated stub. Feedback: ${feedback.trim().slice(
      0,
      120,
    )}</div>`,
    '</body>',
    '</html>',
  ].join('');

  const { htmlSnippet, librariesUsed } = applyInjectionFlows(rawHtml);
  putRun(runId, { htmlSnippet, librariesUsed });

  res.status(200).json({ runId, htmlSnippet, librariesUsed });
});

app.post('/api/model/prompt', (req, res) => {
  const body = req.body ?? {};
  const userPrompt = typeof body.userPrompt === 'string' ? body.userPrompt.trim() : '';
  if (!userPrompt) {
    return res
      .status(422)
      .json(errorBody('validation_failed', 'userPrompt is required'));
  }

  const responseText = buildMockModelPromptText(body);
  const modelResponse = {
    id: `chatcmpl_mock_${Date.now()}`,
    object: 'chat.completion',
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: responseText },
      },
    ],
  };

  return res.status(200).json({
    response: responseText,
    modelResponse,
  });
});

app.get('/api/snippets/:runId.html', (req, res) => {
  const runId = req.params?.runId;
  if (!runId) {
    return res.status(422).json(errorBody('validation_failed', 'runId is required'));
  }
  const existing = getRun(runId);
  if (!existing?.htmlSnippet) {
    return res
      .status(404)
      .json(errorBody('run_not_found', `No snippet found for runId: ${runId}`));
  }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  return res.status(200).send(existing.htmlSnippet);
});

// Health for CLI test
app.get('/health', (_req, res) => {
  res.status(200).json({ ok: true, mock: true });
});

// Mock SSO endpoint
app.get('/sso', (_req, res) => {
  res.sendFile(path.join(publicRoot, 'sso-login.html'));
});

app.listen(PORT, () => {
  console.log(`Mock server listening on http://localhost:${PORT}`);
});
