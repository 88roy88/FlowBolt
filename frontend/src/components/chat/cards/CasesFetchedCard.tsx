import { CheckCircle2, Package } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

interface CaseInfo {
  packageId: string;
  packageName: string;
  dataSchema: string;
  relevantFields?: string;
}

export function CasesFetchedCard({ cases }: { cases: CaseInfo[] }) {
  return (
    <CardWrapper>
      <div className="flex items-center gap-1.5 mb-2 text-xs text-success">
        <CheckCircle2 size={12} />
        {cases.length === 1 ? 'Case data fetched' : `${cases.length} cases fetched`}
      </div>
      {cases.map((c) => (
        <div key={c.packageId} className="mb-2">
          <div className="flex items-center gap-2 p-2 bg-[color-mix(in_srgb,var(--primary)_8%,transparent)] border border-[color-mix(in_srgb,var(--primary)_20%,transparent)] rounded-md mb-1.5">
            <Package size={14} className="text-primary shrink-0" />
            <div className="flex-1">
              <div className="font-medium">{c.packageName}</div>
              <div className="text-[11px] text-muted-foreground">ID: {c.packageId}</div>
            </div>
          </div>
          {c.dataSchema && (
            <div className={`text-xs leading-normal ${c.relevantFields ? 'mb-1' : ''}`}>
              <strong>Data:</strong> {c.dataSchema}
            </div>
          )}
          {c.relevantFields && (
            <div className="text-xs text-muted-foreground leading-normal">
              <strong>Relevant fields:</strong> {c.relevantFields}
            </div>
          )}
        </div>
      ))}
    </CardWrapper>
  );
}
