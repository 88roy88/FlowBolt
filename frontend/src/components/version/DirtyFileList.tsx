import { useTranslation } from 'react-i18next';

export function DirtyFileList({ files }: { files: string[] }) {
  const { t } = useTranslation();
  if (!files.length) return null;

  return (
    <>
      <div className="mt-3 text-[11px] uppercase tracking-wider text-muted-foreground">
        {t('version.dirtyFilesLabel')}
      </div>
      <ul className="mt-1 max-h-32 overflow-y-auto font-mono text-xs opacity-80">
        {files.map((file) => (
          <li key={file}>{file}</li>
        ))}
      </ul>
    </>
  );
}
