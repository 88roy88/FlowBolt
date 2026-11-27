const MAX_VALUE_CHARS = 120;

const shorten = (text: string) => (text.length > MAX_VALUE_CHARS ? `${text.slice(0, MAX_VALUE_CHARS - 1)}…` : text);

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/**
 * Lists a run request's body, shaped `{ cube: { param: value } }`, as `cube.param: value` lines.
 * A body in any other shape, or too long to have arrived whole, is shown as it is.
 */
export function paramLines(body: string | null): string[] {
  if (!body) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return [shorten(body)];
  }
  if (!isObject(parsed) || !Object.values(parsed).every(isObject)) return [shorten(body)];
  return Object.entries(parsed).flatMap(([cube, params]) =>
    Object.entries(params as Record<string, unknown>).map(
      ([name, value]) => `${cube}.${name}: ${shorten(JSON.stringify(value))}`,
    ),
  );
}
