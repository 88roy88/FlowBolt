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
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: 'var(--success)',
      }}>
        <CheckCircle2 size={12} />
        {cases.length === 1 ? 'Case data fetched' : `${cases.length} cases fetched`}
      </div>
      {cases.map((c) => (
        <div key={c.packageId} style={{ marginBottom: '8px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 10px',
            background: 'color-mix(in srgb, var(--accent) 8%, transparent)',
            border: '1px solid color-mix(in srgb, var(--accent) 20%, transparent)',
            borderRadius: '6px',
            marginBottom: '6px',
          }}>
            <Package size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 500 }}>{c.packageName}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>ID: {c.packageId}</div>
            </div>
          </div>
          {c.dataSchema && (
            <div style={{
              fontSize: '12px',
              color: 'var(--text)',
              lineHeight: '1.5',
              marginBottom: c.relevantFields ? '4px' : '0',
            }}>
              <strong>Data:</strong> {c.dataSchema}
            </div>
          )}
          {c.relevantFields && (
            <div style={{
              fontSize: '12px',
              color: 'var(--text-dim)',
              lineHeight: '1.5',
            }}>
              <strong>Relevant fields:</strong> {c.relevantFields}
            </div>
          )}
        </div>
      ))}
    </CardWrapper>
  );
}
