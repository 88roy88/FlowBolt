import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { errorBody } from './errorBody.js';
import {
  searchPackages,
  getPackageMetadata,
  getRunResults,
  getQuickParamsInfo,
} from './packages/index.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb', strict: false }));

const PORT = Number(process.env.MOCK_PORT) || 6001;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const publicRoot = path.join(__dirname, 'public');
app.use(express.static(publicRoot));

/** FLAPI expects a non-empty Authorization header; empty or missing => 401 (mock parity). */
function assertFlapiApiAuthorized(req, res) {
  const raw = req.headers.authorization;
  if (typeof raw !== 'string' || !raw.trim()) {
    res.status(401).json(errorBody('unauthorized', 'Authorization header is required'));
    return false;
  }
  return true;
}

// ——— FLAPI Search ———

function handlePackageSearch(query) {
  const q = String(query ?? '').trim();
  if (!q) {
    return { status: 422, body: errorBody('validation_failed', 'Query parameter "q" is required') };
  }
  if (/^\d+$/.test(q)) {
    const record = getPackageMetadata(q);
    return { status: 200, body: record ? [record] : [] };
  }
  return { status: 200, body: searchPackages(q) };
}

app.get('/package/v1/search/:partial', (req, res) => {
  if (!assertFlapiApiAuthorized(req, res)) return;
  const { status, body } = handlePackageSearch(req.params.partial);
  res.status(status).json(body);
});

// ——— FLAPI Quick Params Info ———

app.get('/package/v1/quick/:packageId', (req, res) => {
  if (!assertFlapiApiAuthorized(req, res)) return;
  res.status(200).json(getQuickParamsInfo(req.params.packageId));
});

// ——— FLAPI Run ———

function runPackageById(req, res) {
  if (!assertFlapiApiAuthorized(req, res)) return;
  const dataSourceId = req.params.packageId;
  if (!dataSourceId?.trim()) {
    return res.status(400).json(errorBody('invalid_data_source_id', 'dataSourceId is required'));
  }
  const result = getRunResults(dataSourceId, req.body);
  if (!result) {
    return res.status(404).json(errorBody('not_found', `No package found for id: ${dataSourceId}`));
  }
  if (result.error) {
    return res.status(422).json(errorBody('missing_required_params', result.error));
  }
  return res.status(200).json(result);
}

app.post('/package/:packageId', runPackageById);
app.post('/package/v3/:packageId', runPackageById);

// ——— Health & SSO ———

app.get('/health', (_req, res) => {
  res.status(200).json({ ok: true, mock: true });
});

app.get('/sso', (_req, res) => {
  res.sendFile(path.join(publicRoot, 'sso-login.html'));
});

app.listen(PORT, () => {
  console.log(`Mock server listening on http://localhost:${PORT}`);
});
