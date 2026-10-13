import { useState } from 'react';
import { Loader2, CheckCircle2, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { FollowUpStep, FileDiff } from '../../../types';
import { CardWrapper } from './CardWrapper';
import { FilesChangedSection } from './FilesChangedSection';
import { getFollowUpToolIcon, getFollowUpToolLabel } from './icons';

function plural(n: number, word: string, pluralWord = `${word}s`) {
  return `${n} ${n === 1 ? word : pluralWord}`;
}

function summarizeSteps(steps: FollowUpStep[]) {
  const ofTools = (tools: FollowUpStep['tool'][]) => steps.filter((s) => s.status === 'completed' && tools.includes(s.tool));
  const uniqueFiles = (tools: FollowUpStep['tool'][]) => new Set(ofTools(tools).map((s) => s.args.path)).size;
  const reads = uniqueFiles(['read_file']);
  const searches = ofTools(['grep', 'glob']).length;
  const edits = uniqueFiles(['write_file', 'edit_file']);
  const parts = [
    reads > 0 && `read ${plural(reads, 'file')}`,
    searches > 0 && `searched ${plural(searches, 'time')}`,
    edits > 0 && `edited ${plural(edits, 'file')}`,
  ].filter(Boolean);
  const summary = parts.length ? parts.join(' · ') : plural(steps.length, 'step');
  return summary.charAt(0).toUpperCase() + summary.slice(1);
}

export function FollowUpProgress({ steps, answer, filesChanged, diffs, isLive }: {
  steps: FollowUpStep[];
  answer?: string;
  filesChanged?: string[];
  diffs?: FileDiff[];
  isLive?: boolean;
}) {
  const inProgress = isLive || steps.some((s) => s.status === 'running');
  // Steps stay visible while the agent works, then collapse to a one-line summary
  const [userExpanded, setUserExpanded] = useState(false);
  const expanded = inProgress || userExpanded;

  return (
    <CardWrapper accent="primary">
      {/* Header */}
      {inProgress ? (
        <div className="flex items-center gap-1.5 mb-3 text-[13px] font-medium text-primary">
          <Loader2 size={14} className="animate-spin" />
          Exploring codebase...
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setUserExpanded((v) => !v)}
          aria-expanded={expanded}
          className={`flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors ${expanded ? 'mb-3' : ''}`}
        >
          <CheckCircle2 size={14} className="shrink-0 text-success" />
          <span className="text-start">{summarizeSteps(steps)}</span>
          <ChevronRight size={14} className={`shrink-0 transition-transform duration-150 rtl:-scale-x-100 ${expanded ? 'rotate-90' : ''}`} />
        </button>
      )}

      {/* Steps */}
      {expanded && <div className="flex flex-col gap-1.5">
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
                <ToolIcon size={14} className="text-muted-foreground shrink-0 mt-px" />
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
      </div>}

      <FilesChangedSection diffs={diffs} files={filesChanged} />

      {/* Answer */}
      {answer && (
        <div className="markdown-content mt-2.5 border-t border-border pt-2.5 text-[13px] leading-relaxed break-words">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
        </div>
      )}
    </CardWrapper>
  );
}
