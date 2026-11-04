// Mirrors the backend: UPLOAD_MAX_ATTACHMENT_BYTES and MAX_ATTACHMENTS_PER_MESSAGE.
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;
export const MAX_ATTACHMENTS = 10;
// Models downscale anything larger, so sending more only costs upload time and tokens.
const MAX_IMAGE_EDGE = 1568;

export type AttachmentKind = 'image' | 'pdf' | 'text';

const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/gif', 'image/webp']);
const TEXT_TYPES = new Set(['text/plain', 'text/csv', 'text/markdown', 'text/tab-separated-values', 'application/json']);
// Browsers leave File.type empty for some of these (notably .md).
const TEXT_EXTENSIONS = new Set(['txt', 'csv', 'md', 'tsv', 'json']);

export const ATTACHMENT_ACCEPT = [...IMAGE_TYPES, 'application/pdf', ...TEXT_TYPES, ...[...TEXT_EXTENSIONS].map((e) => `.${e}`)].join(',');

export function attachmentKind(contentType: string, name: string): AttachmentKind | null {
  if (IMAGE_TYPES.has(contentType)) return 'image';
  if (contentType === 'application/pdf') return 'pdf';
  if (TEXT_TYPES.has(contentType)) return 'text';
  const extension = name.split('.').pop()?.toLowerCase() ?? '';
  return !contentType && TEXT_EXTENSIONS.has(extension) ? 'text' : null;
}

export interface PreparedImage {
  blob: Blob;
  width: number;
  height: number;
}

export async function prepareImage(file: File): Promise<PreparedImage> {
  const bitmap = await createImageBitmap(file);
  const { width, height } = bitmap;
  const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(width, height));
  // GIFs keep their animation, and small images are already fine as they are.
  if (scale === 1 || file.type === 'image/gif') {
    bitmap.close();
    return { blob: file, width, height };
  }
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  canvas.getContext('2d')!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, file.type, 0.9));
  return { blob: blob ?? file, width: canvas.width, height: canvas.height };
}
