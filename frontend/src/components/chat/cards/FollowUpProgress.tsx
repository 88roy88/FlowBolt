import { Loader2, CheckCircle2, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { FollowUpStep, FileDiff } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { DiffBlock } from './DiffBlock';
import { getFollowUpToolIcon, getFollowUpToolLabel } from './icons';

export function FollowUpProgress({ steps, answer, filesChanged, diffs, isLive }: {
  steps: FollowUpStep[];
  answer?: string;
  filesChanged?: string[];
  diffs?: FileDiff[];
  isLive?: boolean;
}) {
  const completed = steps.filter((s) => s.status === 'completed').length;
  const inProgress = isLive || steps.some((s) => s.status === 'running');
  const hasDiffs = diffs && diffs.length > 0;

  return (
    <CardWrapper>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '12px',
        fontSize: '13px',
        fontWeight: 500,
        color: inProgress ? 'var(--accent)' : 'var(--success)',
      }}>
        {inProgress ? (
          <>
            <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
            Exploring codebase...
          </>
        ) : (
          <>
            <CheckCircle2 size={14} />
            Done ({completed} {completed === 1 ? 'step' : 'steps'})
          </>
        )}
      </div>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {steps.map((step) => {
          const ToolIcon = getFollowUpToolIcon(step.tool);
          return (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                padding: '6px 8px',
                borderRadius: '6px',
                background: step.status === 'running' ? 'var(--running-bg)' : 'transparent',
                fontSize: '13px',
                transition: 'background 0.2s',
              }}
            >
              {step.status === 'running' ? (
                <Loader2 size={14} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '1px', animation: 'spin 1s linear infinite' }} />
              ) : (
                <ToolIcon size={14} style={{ color: 'var(--success)', flexShrink: 0, marginTop: '1px' }} />
              )}
              <div style={{ flex: 1, minWidth: 0 }}>
                <span style={{ color: 'var(--text)' }}>
                  {getFollowUpToolLabel(step.tool, step.args, step.status === 'running')}
                </span>
                {step.status === 'completed' && step.resultPreview && step.tool !== 'write_file' && step.tool !== 'edit_file' && (
                  <div style={{
                    marginTop: '4px',
                    padding: '4px 6px',
                    background: 'var(--bg)',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--text-dim)',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-all',
                    maxHeight: '60px',
                    overflow: 'hidden',
                  }}>
                    {step.resultPreview}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Files changed with diffs */}
      {hasDiffs && (
        <div style={{ marginTop: '10px', borderTop: '1px solid var(--border)', paddingTop: '10px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '8px',
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-dim)',
          }}>
            Files changed
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {diffs.map((d) => (
              <DiffBlock key={d.path} fileDiff={d} />
            ))}
          </div>
        </div>
      )}

      {/* Fallback: file list without diffs */}
      {!hasDiffs && filesChanged && filesChanged.length > 0 && (
        <div style={{ marginTop: '10px', borderTop: '1px solid var(--border)', paddingTop: '10px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginBottom: '6px',
            fontSize: '12px',
            fontWeight: 500,
            color: 'var(--text-dim)',
          }}>
            Files changed
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {filesChanged.map((filePath) => (
              <div
                key={filePath}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 8px',
                  borderRadius: '4px',
                  fontSize: '12px',
                }}
              >
                <FileText size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                <span style={{ color: 'var(--text)', fontFamily: 'var(--font-mono)' }}>{filePath}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Answer text */}
      {answer && (
        <div className="markdown-content" style={{
          marginTop: '10px',
          borderTop: '1px solid var(--border)',
          paddingTop: '10px',
          fontSize: '13px',
          lineHeight: '1.6',
          color: 'var(--text)',
          wordBreak: 'break-word',
        }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
        </div>
      )}
    </CardWrapper>
  );
}
