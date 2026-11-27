/** The CSS anchor a data source's AI button gives the shared AI menu. */
export const aiMenuAnchorName = (id: string) => `--data-source-ai-${id.replace(/[^\w-]/g, '_')}`;
