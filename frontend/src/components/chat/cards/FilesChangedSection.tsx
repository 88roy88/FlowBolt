import { FileText } from 'lucide-react';
import type { FileDiff } from '../../../types';
import { DiffBlock } from './DiffBlock';

type Props = { diffs?: FileDiff[]; files?: string[] };

export function FileRows({ diffs, files }: Props) {
  let rows = diffs?.map((d, i) => <DiffBlock key={`${d.path}-${i}`} fileDiff={d} />);

  if (!rows?.length) {
    rows = files?.map((path) => (
      <div key={path} className="flex items-center gap-1.5 px-2 py-1 rounded text-xs">
        <FileText size={12} className="text-primary shrink-0" />
        <span className="font-mono">{path}</span>
      </div>
    ));
  }

  if (!rows?.length) return null;

  return <div className="flex flex-col gap-1.5">{rows}</div>;
}

export function FilesChangedSection({ diffs, files }: Props) {
  if (!diffs?.length && !files?.length) return null;

  return (
    <div className="mt-2.5 border-t border-border pt-2.5">
      <div className="text-xs font-medium text-muted-foreground mb-2">Files changed</div>
      <FileRows diffs={diffs} files={files} />
    </div>
  );
}
