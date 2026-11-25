const TITLE_TAG = /(<title\b[^>]*>)[\s\S]*?<\/title>/i;
const HEAD_END = /<\/head>/i;

function escapeHtml(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Returns `html` with its `<title>` set to `title`, leaving the rest of the page untouched. */
export function withAppTitle(html: string, title: string): string {
  const escaped = escapeHtml(title);
  if (TITLE_TAG.test(html)) return html.replace(TITLE_TAG, (_, open: string) => `${open}${escaped}</title>`);
  if (HEAD_END.test(html)) return html.replace(HEAD_END, (end) => `<title>${escaped}</title>${end}`);
  throw new Error('index.html has no <head> to put a title in');
}
