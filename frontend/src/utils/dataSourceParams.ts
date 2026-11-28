import type { ParamLabel } from '../types';

const MAX_VALUE_CHARS = 120;

const shorten = (text: string) => (text.length > MAX_VALUE_CHARS ? `${text.slice(0, MAX_VALUE_CHARS - 1)}…` : text);

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export interface ParamEntry {
  label: string;
  path: string;
  value: string;
  ambiguous: boolean;
}

/** Expects a body shaped `{ cube: { param: value } }`; any other, including a cut-off one, comes back raw. */
export function describeParams(body: string | null, labels: ParamLabel[]): { entries: ParamEntry[] } | { raw: string } {
  if (!body) return { entries: [] };
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return { raw: shorten(body) };
  }
  if (!isObject(parsed) || !Object.values(parsed).every(isObject)) return { raw: shorten(body) };
  const entries = Object.entries(parsed).flatMap(([cube, params]) =>
    Object.entries(params as Record<string, unknown>).map(([name, value]) => ({
      label: labels.find((p) => p.cube_id === cube && p.name === name)?.label ?? name,
      path: `${cube}.${name}`,
      value: shorten(JSON.stringify(value)),
    })),
  );
  return {
    entries: entries.map((entry) => ({
      ...entry,
      ambiguous: entries.filter((other) => other.label === entry.label).length > 1,
    })),
  };
}

export function formatBody(body: string): string {
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch {
    return body;
  }
}
