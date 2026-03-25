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
    <CardWrapper accent="primary">
      {/* Header */}
      <div className={`flex items-center gap-1.5 mb-3 text-[13px] font-medium ${inProgress ? 'text-primary' : 'text-success'}`}>
        {inProgress ? (
          <>
            <Loader2 size={14} className="animate-spin" />
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
      <div className="flex flex-col gap-1.5">
        {steps.map((step) => {
          const ToolIcon = getFollowUpToolIcon(step.tool);
          return (
            <div
              key={step.id}
              className={`flex items-start gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${
                step.status === 'running' ? 'bg-running-bg' : ''
              }`}
            >
              {step.status === 'running' ? (
                <Loader2 size={14} className="text-primary shrink-0 mt-px animate-spin" />
              ) : (
                <ToolIcon size={14} className="text-success shrink-0 mt-px" />
              )}
              <div className="flex-1 min-w-0">
                <span>{getFollowUpToolLabel(step.tool, step.args, step.status === 'running')}</span>
                {step.status === 'completed' && step.resultPreview && step.tool !== 'write_file' && step.tool !== 'edit_file' && (
                  <div className="mt-1 px-1.5 py-1 bg-background rounded text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-all max-h-[60px] overflow-hidden">
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
        <div className="mt-2.5 border-t border-border pt-2.5">
          <div className="text-xs font-medium text-muted-foreground mb-2">Files changed</div>
          <div className="flex flex-col gap-1.5">
            {diffs.map((d) => <DiffBlock key={d.path} fileDiff={d} />)}
          </div>
        </div>
      )}

      {/* Fallback file list */}
      {!hasDiffs && filesChanged && filesChanged.length > 0 && (
        <div className="mt-2.5 border-t border-border pt-2.5">
          <div className="text-xs font-medium text-muted-foreground mb-1.5">Files changed</div>
          <div className="flex flex-col gap-0.5">
            {filesChanged.map((filePath) => (
              <div key={filePath} className="flex items-center gap-1.5 px-2 py-1 rounded text-xs">
                <FileText size={12} className="text-primary shrink-0" />
                <span className="font-mono">{filePath}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Answer */}
      {answer && (
        <div className="markdown-content mt-2.5 border-t border-border pt-2.5 text-[13px] leading-relaxed break-words">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
        </div>
      )}
    </CardWrapper>
  );
}
