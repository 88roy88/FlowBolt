import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import swagger from '@fastify/swagger';
import swaggerUI from '@fastify/swagger-ui';
import { TypeBoxTypeProvider } from '@fastify/type-provider-typebox';
import { Type } from '@sinclair/typebox';

const __dirname = dirname(fileURLToPath(import.meta.url));
import {
  ErrorBodySchema,
  SearchResultSchema,
  PackageMetadataSchema,
  QuickParamDefinitionSchema,
  RunResultSchema,
  HealthSchema,
  errorBody,
} from './schemas';
import {
  searchPackages,
  getRunResults,
  getQuickParamsInfo,
  getPackageFullMetadata,
} from './packages';

const PORT = Number(process.env.MOCK_PORT) || 6001;

// Dev RSA private key for signing JWT tokens (RS256).
// The corresponding public key goes in AIB_AUTH_JWT_PUBLIC_KEY in the backend .env.
// Override with MOCK_JWT_PRIVATE_KEY env var for non-dev environments.
const DEV_JWT_PRIVATE_KEY =
  process.env.MOCK_JWT_PRIVATE_KEY ||
  `-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDmuU+ys5zolViz
qOoOLOPEM6qKw1O2zvLDrp17LN70fPcILlqLG8+ucCJG85TvlxHo9BjNe08wKxl+
V+YguAkF88CVFzvIXbXUkFjq70irorck3tw3KEfv0Zbp0MxnKog1cx5rzh5CYHBt
AoeCrAVAX6EG0gZ9UoBqlGIFtAARxgUVUWNDasfhzICI8vAei0oc/4Br3/0TUt7e
brSk0UBnWIn/ui8ubWjQQ1NApsUTLNdu6l63Z/ORSfyNq49UM6lbEXGwQjjt1WVv
kllQue6zNffSbcRAPmUONs0MxRWajbd6uJCMOFqaGvtFuHbo3wOLpaRm/oafOxuk
+Z2munZPAgMBAAECggEAAXjnQEp5hgzSuK34QftMjMddOQhCc+Uukv8XQPgqIadD
SeMTb6KcZaf2uaGUrrhPd4wVm6IQzeVIgvZ7bac4letWeRBH4/rTgTXwMbeX+bho
SmAkFmbRM3+Qr5DfudZn17RFwNLBsKy+EVDPao8Mc+4bfSUNjSX5bQF7ZD8gADA4
yxYCWEtbFW0m6Tu+VRLMfiIsnwfAiPlKm6J4J06eCTa+MX17AR6KOWYe7eWfGDme
b3BPvLajw1+AGtY7Mtqbvl+PQhdOPoCdqdKC81cyuJ68YrofbY7dohYl+Wpg7ytQ
QyKHif8NO0RPOBhxpe13ZbF2jeyPCUTSWQXTObRWYQKBgQD39hLhpqaR52U0J7jY
09NwLYSHrs3vAzdXDM6G8tJFMFG3F/yQoYQRt7C8VZx+l5QUZHfFBlN/VoQFlCDc
TBTic2ZWY25Q6IG/EPCSu4+Wft2I4W4GYukHs9jMtUgWHPEVzZG9gGWRJi1DYNkF
FZrx+wpCcP+6qZlx47D0pApafwKBgQDuNC2Xlhf3Th+XzifeuBb/7he1haBW1NXh
HXwRrGHRFIOykEfoIXPXrzHKseVOiN8+iXCIqKV8bK+DMeYCjwh/DNLggMKPny8Q
fhyWzaMFrQaloPx2rv9sr5bk0TZDtz8y2RviBy0+ykcKCorhYDwIxlEJ8Sa7qNUy
HT62xAbcMQKBgQDXxVz22TLXghlSAkLbA7FZS3KpM1bmZtEQQgex7LlHFd31yryw
CqzHUiZMLN9qVXK5MBf87h1YkKt/wz+5E8eUqsDh6dJEO58z6YS+2tH/LtSOWUSJ
8CZB2qGMuS9KdtLfmyv4UDOR1DvNBwiyYPOdIEv0NyqBfzYUogMJT3nm9wKBgQDG
iuUpgShOsGYy4NlokSZSgcBvQ4bGeTYgIbRFAtqxK5kt34af3CozL0qgOTD5CaqR
9HrA3Vi54dlUz+V4YoHha+3kxE3m6faPl536sEHePD7bFNj5j5lEnQJ3jE3fmUBr
AH12Iyc6O92EaA8kFVNUuP/Y+pCfP/UbhTa9nZxeMQKBgQDIepUV+2LblsC7CIae
2N1drFIDvYYJz0h+fJEMO6rNen2JbDm10SbHChyaKT1/RX5KqdiUrKgT/MmquxyT
3HZCzITfN1nbtE4791So44Ccj6lbRYJzY7N3AOgRcBYaBLSqsgPe+1uYymhUXRQl
8+TyOXMa9uhwS4VHilRUZ7Tjmg==
-----END PRIVATE KEY-----`;

const _jwtBase64url = (obj: unknown): string =>
  Buffer.from(JSON.stringify(obj)).toString('base64url');

const signJwt = (claims: Record<string, unknown>): string => {
  const header = _jwtBase64url({ alg: 'RS256', typ: 'JWT' });
  const payload = _jwtBase64url(claims);
  const data = `${header}.${payload}`;
  const sig = crypto.createSign('SHA256').update(data).sign(DEV_JWT_PRIVATE_KEY, 'base64url');
  return `${data}.${sig}`;
};

const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  try {
    return JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }
};

const server = Fastify({ logger: false }).withTypeProvider<TypeBoxTypeProvider>();

// Register CORS
await server.register(cors);

// Serve static assets (mock SSO login page, etc.) from /public on the /public/* URL prefix.
await server.register(fastifyStatic, {
  root: join(__dirname, 'public'),
  prefix: '/public/',
});

// Register Swagger
await server.register(swagger, {
  openapi: {
    info: {
      title: 'FLAPI Mock Server',
      description: 'Mock server for Flow API (FLAPI) - mimics internal FLAPI for development',
      version: '0.1.0',
    },
    servers: [{ url: `http://localhost:${PORT}` }],
    components: {
      securitySchemes: {
        bearerAuth: {
          type: 'http',
          scheme: 'bearer',
          bearerFormat: 'JWT',
        },
      },
    },
    tags: [
      { name: 'Search', description: 'Package search endpoints' },
      { name: 'Run', description: 'Package execution endpoints' },
      { name: 'Metadata', description: 'Package metadata endpoints' },
      { name: 'Health', description: 'Health check endpoints' },
    ],
  },
});

// Register Swagger UI
await server.register(swaggerUI, {
  routePrefix: '/api-docs',
  uiConfig: {
    docExpansion: 'list',
    deepLinking: false,
  },
});

// Paths that don't require the Authorization header. The SSO login page
// sits behind no auth for obvious reasons — it's what callers hit to *get*
// a token in the first place.
const PUBLIC_PATH_PREFIXES = ['/api-docs', '/documentation', '/public/', '/sso'];
const PUBLIC_PATHS = new Set(['/health']);

server.addHook('preHandler', async (request, reply) => {
  const url = request.url.split('?', 1)[0];
  if (PUBLIC_PATHS.has(url) || PUBLIC_PATH_PREFIXES.some((p) => url.startsWith(p))) {
    return;
  }

  const auth = request.headers.authorization;
  if (!auth || typeof auth !== 'string' || !auth.trim()) {
    return reply.status(401).send(errorBody('unauthorized', 'Authorization header is required'));
  }
  const token = auth.replace(/^Bearer\s+/i, '').trim();
  const payload = decodeJwtPayload(token);
  if (payload && typeof payload.exp === 'number') {
    if (payload.exp <= Math.floor(Date.now() / 1000)) {
      return reply.status(401).send(errorBody('token_expired', 'Token has expired'));
    }
  }
});

// Convenience redirect so callers (frontend, backend config) can link to /sso
// instead of /public/sso-login.html. The prefix /sso is also in the auth allowlist.
server.get('/sso', async (request, reply) => {
  const qs = request.url.includes('?') ? request.url.slice(request.url.indexOf('?')) : '';
  return reply.redirect(`/public/sso-login.html${qs}`, 302);
});

// Issues a signed JWT for the mock SSO login form
server.post(
  '/sso/token',
  {
    schema: {
      tags: ['Auth'],
      description: 'Issue a signed JWT for the mock SSO login form',
      body: Type.Partial(
        Type.Object({
          uniqueId: Type.String(),
          givenName: Type.String(),
          surname: Type.String(),
          expiresInSeconds: Type.Number(),
          issuer: Type.String(),
        }),
      ),
      response: {
        200: Type.Object({
          token: Type.String(),
          claims: Type.Record(Type.String(), Type.Unknown()),
        }),
        422: ErrorBodySchema,
        500: ErrorBodySchema,
      },
    },
  },
  async (request, reply) => {
    const { uniqueId, givenName, surname, expiresInSeconds, issuer } = request.body ?? {};
    if (!uniqueId?.trim()) {
      return reply.status(422).send(errorBody('validation_failed', 'uniqueId is required'));
    }
    const claimPrefix = 'https://issuer.example/v1/claims/';
    const expSeconds = Number.isFinite(Number(expiresInSeconds)) ? Number(expiresInSeconds) : 3600;
    const claims: Record<string, unknown> = {
      exp: Math.floor(Date.now() / 1000) + expSeconds,
      iss: issuer?.trim() || 'flapi-mock',
      [claimPrefix + 'UniqueID']: uniqueId.trim(),
    };
    if (givenName?.trim()) claims[claimPrefix + 'givenname'] = givenName.trim();
    if (surname?.trim()) claims[claimPrefix + 'surname'] = surname.trim();
    try {
      return reply.send({ token: signJwt(claims), claims });
    } catch {
      return reply.status(500).send(errorBody('sign_failed', 'Failed to sign token'));
    }
  },
);

// ——— FLAPI Search ———

server.get(
  '/package/v1/search/:partial',
  {
    schema: {
      tags: ['Search'],
      description: 'Search for packages by name or ID',
      security: [{ bearerAuth: [] }],
      params: Type.Object({
        partial: Type.String({ description: 'Package name or ID to search for' }),
      }),
      response: {
        200: Type.Array(SearchResultSchema),
        401: ErrorBodySchema,
        422: ErrorBodySchema,
      },
    },
  },
  async (request, reply) => {
    const q = request.params.partial.trim();
    if (!q) {
      return reply.status(422).send(errorBody('validation_failed', 'Query parameter "q" is required'));
    }

    return searchPackages(q);
  }
);

// ——— FLAPI Quick Params Info ———

server.get(
  '/package/v1/quick/:packageId',
  {
    schema: {
      tags: ['Metadata'],
      description: 'Get quick parameters info for a package',
      security: [{ bearerAuth: [] }],
      params: Type.Object({
        packageId: Type.String({ description: 'Package ID' }),
      }),
      response: {
        200: Type.Record(Type.String(), Type.Array(QuickParamDefinitionSchema)),
        401: ErrorBodySchema,
      },
    },
  },
  async (request) => {
    return getQuickParamsInfo(request.params.packageId);
  }
);

// ——— FLAPI Package Metadata ———

server.get(
  '/package/v2/:packageId',
  {
    schema: {
      tags: ['Metadata'],
      description: 'Get full package metadata including queries and fields',
      security: [{ bearerAuth: [] }],
      params: Type.Object({
        packageId: Type.String({ description: 'Package ID' }),
      }),
      response: {
        200: PackageMetadataSchema,
        401: ErrorBodySchema,
        404: ErrorBodySchema,
      },
    },
  },
  async (request, reply) => {
    const metadata = getPackageFullMetadata(request.params.packageId);
    if (!metadata) {
      return reply.status(404).send(errorBody('not_found', `No package found for id: ${request.params.packageId}`));
    }
    return metadata;
  }
);

// ——— FLAPI Run ———

const runPackageSchema = {
  tags: ['Run'],
  description: 'Execute a package with optional quick parameters',
  security: [{ bearerAuth: [] }],
  params: Type.Object({
    packageId: Type.String({ description: 'Package ID' }),
  }),
  body: Type.Record(Type.String(), Type.Unknown(), { description: 'Quick parameters (optional)' }),
  response: {
    200: RunResultSchema,
    400: ErrorBodySchema,
    401: ErrorBodySchema,
    404: ErrorBodySchema,
    422: ErrorBodySchema,
  },
};

const runPackageHandler = async (request: any, reply: any) => {
  const dataSourceId = request.params.packageId;
  if (!dataSourceId?.trim()) {
    return reply.status(400).send(errorBody('invalid_data_source_id', 'dataSourceId is required'));
  }

  const result = getRunResults(dataSourceId, request.body);
  if (!result) {
    return reply.status(404).send(errorBody('not_found', `No package found for id: ${dataSourceId}`));
  }
  if ('error' in result) {
    return reply.status(421).send(errorBody('missing_required_params', result.error));
  }

  return result;
};

// Register run endpoint with both v3 and legacy routes
server.post('/package/v3/:packageId', { schema: runPackageSchema }, runPackageHandler);
server.post('/package/:packageId', { schema: runPackageSchema }, runPackageHandler);

// ——— Health ———

server.get(
  '/health',
  {
    schema: {
      tags: ['Health'],
      description: 'Health check endpoint',
      response: {
        200: HealthSchema,
      },
    },
  },
  async () => {
    return { ok: true, mock: true };
  }
);

// ——— Start Server ———

try {
  await server.listen({ port: PORT, host: '0.0.0.0' });
  console.log(`Mock server listening on http://localhost:${PORT}`);
  console.log(`Swagger UI available at http://localhost:${PORT}/api-docs`);
} catch (err) {
  server.log.error(err);
  process.exit(1);
}
