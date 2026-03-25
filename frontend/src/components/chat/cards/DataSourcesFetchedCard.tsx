import { CheckCircle2, Package } from 'lucide-react';
import { CardWrapper } from './CardWrapper';

interface DataSourceInfo {
  dataSourceId: string;
  dataSourceName: string;
  dataSchema: string;
  relevantFields?: string;
}

export function DataSourcesFetchedCard({ dataSources }: { dataSources: DataSourceInfo[] }) {
  return (
    <CardWrapper accent="primary">
      <div className="flex items-center gap-1.5 mb-2 text-xs text-success">
        <CheckCircle2 size={12} />
        {dataSources.length === 1 ? 'Data source fetched' : `${dataSources.length} data sources fetched`}
      </div>
      {dataSources.map((ds) => (
        <div key={ds.dataSourceId} className="mb-2">
          <div className="flex items-center gap-2 p-2 bg-[color-mix(in_srgb,var(--primary)_8%,transparent)] border border-[color-mix(in_srgb,var(--primary)_20%,transparent)] rounded-md mb-1.5">
            <Package size={14} className="text-primary shrink-0" />
            <div className="flex-1">
              <div className="font-medium">{ds.dataSourceName}</div>
              <div className="text-[11px] text-muted-foreground">ID: {ds.dataSourceId}</div>
            </div>
          </div>
          {ds.dataSchema && (
            <div className={`text-xs leading-normal ${ds.relevantFields ? 'mb-1' : ''}`}>
              <strong>Data:</strong> {ds.dataSchema}
            </div>
          )}
          {ds.relevantFields && (
            <div className="text-xs text-muted-foreground leading-normal">
              <strong>Relevant fields:</strong> {ds.relevantFields}
            </div>
          )}
        </div>
      ))}
    </CardWrapper>
  );
}
