/**
 * Consistent error response shape per server-spec §5.
 * @param {string} code
 * @param {string} message
 * @param {unknown} [details]
 * @returns {{ error: { code: string, message: string, details?: unknown } }}
 */
export const errorBody = (code, message, details) => {
  const body = { error: { code, message } };
  if (details !== undefined) body.error.details = details;
  return body;
};
