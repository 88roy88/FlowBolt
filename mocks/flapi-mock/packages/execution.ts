import type { QuickParamDefinition } from '../schemas.js';
import { packageById } from './registry.js';

interface QuickParams {
  [paramName: string]: unknown;
}

function extractQuickParams(body: unknown): QuickParams {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return {};

  const extracted: QuickParams = {};
  for (const cubeParams of Object.values(body)) {
    if (cubeParams && typeof cubeParams === 'object' && !Array.isArray(cubeParams)) {
      Object.assign(extracted, cubeParams);
    }
  }
  return extracted;
}

export function getRunResults(
  dataSourceId: string,
  body: unknown
): { results: Record<string, unknown> } | { error: string } | null {
  const id = String(dataSourceId).trim();
  const pkg = packageById.get(id);
  if (!pkg) return null;

  const quickParams = extractQuickParams(body);
  const validationResult = pkg.validateAndApplyDefaults(quickParams);

  if ('error' in validationResult) {
    return { error: validationResult.error };
  }

  return { results: pkg.getResults(validationResult.params) };
}

export function getQuickParamsInfo(packageId: string): Record<string, QuickParamDefinition[]> {
  const pkg = packageById.get(String(packageId).trim());
  return pkg?.quickParams || {};
}
