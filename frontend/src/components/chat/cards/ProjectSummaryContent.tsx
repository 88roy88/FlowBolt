import { Sparkles, FileText, Package } from 'lucide-react';
import type { ProjectSummary } from '../../../types';

export function ProjectSummaryContent({ summary }: { summary: ProjectSummary }) {
  return (
    <>
      <p className="mb-3 leading-relaxed">{summary.summary}</p>

      {summary.tech_stack && summary.tech_stack.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-muted-foreground mb-1.5">Tech Stack</div>
          <div className="flex flex-wrap gap-1">
            {summary.tech_stack.map((tech, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-background border border-border rounded text-[11px] text-primary">
                <Package size={10} />
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.features && summary.features.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-semibold text-muted-foreground mb-1.5">Features</div>
          <div className="flex flex-col gap-1">
            {summary.features.map((feature, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <Sparkles size={12} className="text-primary shrink-0 mt-0.5" />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary.file_overview && Object.keys(summary.file_overview).length > 0 && (
        <div>
          <div className="text-xs font-semibold text-muted-foreground mb-1.5">Key Files</div>
          <div className="flex flex-col gap-1">
            {Object.entries(summary.file_overview).map(([file, description]) => (
              <div key={file} className="flex items-start gap-1.5 text-xs">
                <FileText size={12} className="text-muted-foreground shrink-0 mt-0.5" />
                <span>
                  <strong>{file}</strong>
                  <span className="text-muted-foreground"> — {description}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
