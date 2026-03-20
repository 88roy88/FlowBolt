import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, TerminalSquare, Sparkles, CheckCircle2, XCircle, ArrowRight, Check, X, Package, AlertTriangle, ChevronDown, ChevronRight, Loader2, Search, Wrench, Save, TestTube, RefreshCw, FolderSearch, Pencil } from 'lucide-react';
import type { Message, PlanOverview, ExecutionTask, ProjectSummary, FixStep, FollowUpStep, FileDiff } from '../../types';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

function PlanOverviewCard({ overview, accepted }: { overview: PlanOverview; accepted: boolean }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: accepted ? 'var(--success)' : 'var(--text-dim)',
      }}>
        {accepted ? <Check size={12} /> : <X size={12} />}
        {accepted ? 'Plan accepted' : 'Plan rejected'}
      </div>
      <p style={{ marginBottom: '8px', lineHeight: '1.5' }}>{overview.summary}</p>
      {overview.features && overview.features.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '8px' }}>
          {overview.features.map((f, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
              <Sparkles size={12} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
              <span><strong>{f.title}</strong> — {f.description}</span>
            </div>
          ))}
        </div>
      )}
      {overview.decisions && overview.decisions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {overview.decisions.map((d) => (
            <div key={d.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-dim)' }}>
              <ArrowRight size={10} style={{ flexShrink: 0 }} />
              <span><strong>{d.title}:</strong> {d.chosen}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TaskProgressCard({ tasks }: { tasks: ExecutionTask[] }) {
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;
  const total = tasks.length;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: failed > 0 ? 'var(--danger)' : 'var(--success)',
      }}>
        {failed > 0 ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
        {failed > 0
          ? `Built ${completed}/${total} tasks (${failed} failed)`
          : `Built ${completed}/${total} tasks`}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        {tasks.map((task) => (
          <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
            {task.status === 'completed' ? (
              <CheckCircle2 size={11} style={{ color: 'var(--success)', flexShrink: 0 }} />
            ) : task.status === 'failed' ? (
              <XCircle size={11} style={{ color: 'var(--danger)', flexShrink: 0 }} />
            ) : (
              <span style={{ width: 11, height: 11, flexShrink: 0 }} />
            )}
            <span style={{ color: task.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>
              {task.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function DesignCompleteCard({ architecture, ux }: { architecture: boolean; ux: boolean }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '6px' }}>
        Design complete
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {architecture ? (
            <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
          ) : (
            <XCircle size={13} style={{ color: 'var(--danger)' }} />
          )}
          <span>Architecture</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {ux ? (
            <CheckCircle2 size={13} style={{ color: 'var(--success)' }} />
          ) : (
            <XCircle size={13} style={{ color: 'var(--danger)' }} />
          )}
          <span>UI/UX</span>
        </div>
      </div>
    </div>
  );
}

function CasesFetchedCard({ cases }: { cases: { packageId: string; packageName: string; dataSchema: string; relevantFields?: string }[] }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
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
    </div>
  );
}

function ProjectSummaryCard({ summary }: { summary: ProjectSummary }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: 'var(--success)',
      }}>
        <CheckCircle2 size={12} />
        Project complete
      </div>

      <p style={{ marginBottom: '12px', lineHeight: '1.5' }}>{summary.summary}</p>

      {summary.tech_stack && summary.tech_stack.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '4px' }}>
            Tech Stack
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
            {summary.tech_stack.map((tech, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '2px 8px',
                  background: 'var(--bg)',
                  border: '1px solid var(--border)',
                  borderRadius: '4px',
                  fontSize: '11px',
                  color: 'var(--accent)',
                }}
              >
                <Package size={10} />
                {tech}
              </span>
            ))}
          </div>
        </div>
      )}

      {summary.features && summary.features.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '4px' }}>
            Features
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {summary.features.map((feature, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                <Sparkles size={12} style={{ color: 'var(--accent)', flexShrink: 0, marginTop: '2px' }} />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {summary.file_overview && Object.keys(summary.file_overview).length > 0 && (
        <div>
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '4px' }}>
            Key Files
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {Object.entries(summary.file_overview).map(([file, description]) => (
              <div key={file} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', fontSize: '12px' }}>
                <FileText size={12} style={{ color: 'var(--text-dim)', flexShrink: 0, marginTop: '2px' }} />
                <span>
                  <strong style={{ color: 'var(--text)' }}>{file}</strong>
                  <span style={{ color: 'var(--text-dim)' }}> — {description}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ErrorFixRequestCard({ errorMessage, errorFile, errorLine, errorStack }: { errorMessage: string; errorFile?: string; errorLine?: number; errorStack?: string }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: '#f38ba8',
      }}>
        <AlertTriangle size={14} />
        Fix error request
      </div>

      {errorFile && (
        <div style={{ marginBottom: '8px', fontSize: '12px', color: 'var(--text-dim)' }}>
          <FileText size={12} style={{ display: 'inline', marginRight: '4px' }} />
          <strong>{errorFile}</strong>
          {errorLine && <span>:{errorLine}</span>}
        </div>
      )}

      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          padding: '6px',
          marginBottom: isExpanded ? '8px' : '0',
          borderRadius: '6px',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
        }}
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span style={{ fontSize: '12px', fontWeight: 600 }}>Error details</span>
      </div>

      {isExpanded && (
        <div style={{
          padding: '8px',
          background: 'var(--bg)',
          borderRadius: '6px',
          fontSize: '12px',
          lineHeight: '1.5',
        }}>
          <div style={{ marginBottom: errorStack ? '8px' : '0' }}>
            <strong style={{ color: '#f38ba8' }}>Message:</strong>
            <div style={{ marginTop: '4px', color: 'var(--text)' }}>{errorMessage}</div>
          </div>

          {errorStack && (
            <div>
              <strong style={{ color: 'var(--text-dim)' }}>Stack trace:</strong>
              <pre style={{
                marginTop: '4px',
                padding: '8px',
                background: 'var(--surface)',
                borderRadius: '4px',
                fontSize: '11px',
                overflow: 'auto',
                maxHeight: '200px',
                fontFamily: 'monospace',
              }}>
                {errorStack}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function getStepIcon(step: FixStep['step']) {
  switch (step) {
    case 'discover':
      return Search;
    case 'generate':
      return Wrench;
    case 'write':
      return Save;
    case 'validate':
      return TestTube;
    case 'retry':
      return RefreshCw;
  }
}

function FixProgressCard({ steps, content }: { steps: FixStep[]; content?: string }) {
  const completed = steps.filter((s) => s.status === 'completed').length;
  const failed = steps.filter((s) => s.status === 'failed').length;
  const total = steps.length;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '12px 14px',
      fontSize: '13px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: failed > 0 ? 'var(--danger)' : 'var(--success)',
      }}>
        {failed > 0 ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
        {failed > 0
          ? `Fixed error with ${failed} validation failure${failed > 1 ? 's' : ''}`
          : `Fixed error (${completed}/${total} steps)`}
      </div>

      {/* Explanation text */}
      {content && (
        <div style={{
          marginBottom: '8px',
          padding: '8px',
          background: 'var(--bg)',
          borderRadius: '6px',
          fontSize: '12px',
          lineHeight: '1.5',
          color: 'var(--text)',
        }}>
          {content}
        </div>
      )}

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        {steps.map((step) => {
          const StepIcon = getStepIcon(step.step);
          return (
            <div key={step.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
              {step.status === 'running' ? (
                <Loader2 size={11} style={{ color: 'var(--accent)', flexShrink: 0, animation: 'spin 1s linear infinite' }} />
              ) : step.status === 'completed' ? (
                <StepIcon size={11} style={{ color: 'var(--success)', flexShrink: 0 }} />
              ) : (
                <XCircle size={11} style={{ color: 'var(--danger)', flexShrink: 0 }} />
              )}
              <span style={{ color: step.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>
                {step.message}
              </span>
            </div>
          );
        })}
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

function getFollowUpToolIcon(tool: FollowUpStep['tool']) {
  switch (tool) {
    case 'grep':
      return Search;
    case 'glob':
      return FolderSearch;
    case 'read_file':
      return FileText;
    case 'write_file':
      return Save;
    case 'edit_file':
      return Pencil;
  }
}

function getFollowUpToolLabel(tool: FollowUpStep['tool'], args: Record<string, string>, isRunning?: boolean) {
  switch (tool) {
    case 'grep':
      return isRunning
        ? `Searching for '${args.pattern || ''}'${args.path && args.path !== '/' ? ` in ${args.path}` : ''}`
        : `Searched for '${args.pattern || ''}'${args.path && args.path !== '/' ? ` in ${args.path}` : ''}`;
    case 'glob':
      return isRunning ? `Finding files: ${args.pattern || ''}` : `Found files: ${args.pattern || ''}`;
    case 'read_file':
      return isRunning ? `Reading ${args.path || ''}` : `Read ${args.path || ''}`;
    case 'write_file':
      return isRunning ? `Writing ${args.path || ''}` : `Wrote ${args.path || ''}`;
    case 'edit_file':
      return isRunning ? `Editing ${args.path || ''}` : `Edited ${args.path || ''}`;
  }
}

function DiffBlock({ fileDiff }: { fileDiff: FileDiff }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const lines = fileDiff.diff.split('\n');
  // Count additions and deletions (skip header lines starting with --- +++ @@)
  let additions = 0;
  let deletions = 0;
  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) additions++;
    else if (line.startsWith('-') && !line.startsWith('---')) deletions++;
  }

  return (
    <div style={{
      border: '1px solid var(--border)',
      borderRadius: '6px',
      overflow: 'hidden',
    }}>
      <div
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '6px 10px',
          background: 'var(--bg)',
          cursor: 'pointer',
          fontSize: '12px',
        }}
      >
        {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <FileText size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
        <span style={{ fontFamily: 'var(--font-mono)', flex: 1 }}>{fileDiff.path}</span>
        <span style={{ display: 'flex', gap: '6px', fontSize: '11px', flexShrink: 0 }}>
          {additions > 0 && <span style={{ color: '#a6e3a1' }}>+{additions}</span>}
          {deletions > 0 && <span style={{ color: '#f38ba8' }}>-{deletions}</span>}
        </span>
      </div>
      {isExpanded && (
        <div style={{
          overflow: 'auto',
          maxHeight: '300px',
          fontSize: '11px',
          fontFamily: 'var(--font-mono)',
          lineHeight: '1.5',
        }}>
          {lines.map((line, i) => {
            // Skip empty trailing line
            if (i === lines.length - 1 && line === '') return null;
            let bg = 'transparent';
            let color = 'var(--text-dim)';
            if (line.startsWith('+') && !line.startsWith('+++')) {
              bg = 'rgba(166, 227, 161, 0.1)';
              color = '#a6e3a1';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
              bg = 'rgba(243, 139, 168, 0.1)';
              color = '#f38ba8';
            } else if (line.startsWith('@@')) {
              color = 'var(--accent)';
            }
            return (
              <div
                key={i}
                style={{
                  padding: '0 10px',
                  background: bg,
                  color,
                  whiteSpace: 'pre',
                  minHeight: '18px',
                }}
              >
                {line}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

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
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '14px 16px',
      fontSize: '13px',
    }}>
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

      {/* Steps with previews */}
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
                background: step.status === 'running' ? 'rgba(137, 180, 250, 0.08)' : 'transparent',
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

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user';

  // Skip completely empty messages (no content, no card, no actions)
  if (!message.content && !message.agentCard && !message.actions?.length && !isStreaming) {
    return null;
  }

  // Agent card messages (no bubble wrapper — the card IS the message)
  if (message.agentCard) {
    return (
      <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
        <div style={{ maxWidth: '85%' }}>
          {message.agentCard.type === 'cases_fetched' && (
            <CasesFetchedCard cases={message.agentCard.cases} />
          )}
          {message.agentCard.type === 'package_fetched' && (
            <CasesFetchedCard cases={[{
              packageId: message.agentCard.packageId,
              packageName: message.agentCard.packageName,
              dataSchema: message.agentCard.dataSchema,
              relevantFields: message.agentCard.relevantFields,
            }]} />
          )}
          {message.agentCard.type === 'design_complete' && (
            <DesignCompleteCard architecture={message.agentCard.architecture} ux={message.agentCard.ux} />
          )}
          {message.agentCard.type === 'plan_overview' && (
            <PlanOverviewCard overview={message.agentCard.overview} accepted={message.agentCard.accepted} />
          )}
          {message.agentCard.type === 'task_progress' && (
            <TaskProgressCard tasks={message.agentCard.tasks} />
          )}
          {message.agentCard.type === 'project_summary' && (
            <ProjectSummaryCard summary={message.agentCard.summary} />
          )}
          {message.agentCard.type === 'error_fix_request' && (
            <ErrorFixRequestCard
              errorMessage={message.agentCard.errorMessage}
              errorFile={message.agentCard.errorFile}
              errorLine={message.agentCard.errorLine}
              errorStack={message.agentCard.errorStack}
            />
          )}
          {message.agentCard.type === 'fix_progress' && (
            <FixProgressCard steps={message.agentCard.steps} content={message.content} />
          )}
          {message.agentCard.type === 'followup_progress' && (
            <FollowUpProgress steps={message.agentCard.steps} answer={message.agentCard.answer} filesChanged={message.agentCard.filesChanged} diffs={message.agentCard.diffs} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '85%',
        padding: '10px 14px',
        borderRadius: '12px',
        background: isUser ? 'var(--user-bubble)' : 'var(--assistant-bubble)',
        border: `1px solid ${isUser ? 'var(--border)' : 'var(--border)'}`,
        fontSize: '14px',
        lineHeight: '1.6',
      }}>
        {isUser && message.cases && message.cases.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: 6 }}>
            {message.cases.map((c) => (
              <div key={c.id} style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '3px 8px',
                borderRadius: 999,
                background: 'rgba(76, 167, 255, 0.14)',
                border: '1px solid rgba(76, 167, 255, 0.25)',
                color: 'var(--text)',
                fontSize: 12,
              }}>
                <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>Case</span>
                <span style={{ fontWeight: 600 }}>{c.name}</span>
                <span style={{ color: 'var(--text-dim)' }}>#{c.id}</span>
              </div>
            ))}
          </div>
        )}
        {/* Backward compat for old single-package messages */}
        {isUser && !message.cases && message.package && (
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '3px 8px',
            borderRadius: 999,
            background: 'rgba(76, 167, 255, 0.14)',
            border: '1px solid rgba(76, 167, 255, 0.25)',
            color: 'var(--text)',
            fontSize: 12,
            marginBottom: 6,
          }}>
            <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>Case</span>
            <span style={{ fontWeight: 600 }}>{message.package.name}</span>
            <span style={{ color: 'var(--text-dim)' }}>#{message.package.id}</span>
          </div>
        )}
        {isUser ? (
          <p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
        ) : (
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ children, className, ...props }) {
                  const isInline = !className;
                  if (isInline) {
                    return (
                      <code
                        style={{
                          background: 'var(--bg)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontSize: '13px',
                          fontFamily: 'var(--font-mono)',
                        }}
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  }
                  return (
                    <pre style={{
                      background: 'var(--bg)',
                      padding: '12px',
                      borderRadius: '6px',
                      overflow: 'auto',
                      fontSize: '13px',
                      fontFamily: 'var(--font-mono)',
                      margin: '8px 0',
                    }}>
                      <code {...props}>{children}</code>
                    </pre>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            {isStreaming && (
              <span style={{
                display: 'inline-block',
                width: '6px',
                height: '16px',
                background: 'var(--accent)',
                marginLeft: '2px',
                animation: 'blink 1s step-end infinite',
                verticalAlign: 'text-bottom',
              }} />
            )}
          </div>
        )}

        {/* Action indicators */}
        {message.actions && message.actions.length > 0 && (
          <div style={{
            marginTop: '8px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}>
            {message.actions.map((action, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12px',
                  color: 'var(--text-dim)',
                  padding: '4px 8px',
                  background: 'var(--bg)',
                  borderRadius: '4px',
                }}
              >
                {action.type === 'file' ? (
                  <>
                    <FileText size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    <span className="truncate">{action.path}</span>
                  </>
                ) : (
                  <>
                    <TerminalSquare size={14} style={{ color: 'var(--success)', flexShrink: 0 }} />
                    <span className="truncate">{action.command}</span>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`
        @keyframes blink {
          50% { opacity: 0; }
        }
        .markdown-content p { margin: 4px 0; }
        .markdown-content ul, .markdown-content ol { padding-left: 20px; margin: 4px 0; }
        .markdown-content table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 12px; }
        .markdown-content th, .markdown-content td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }
        .markdown-content th { background: var(--bg); font-weight: 600; }
        .markdown-content tr:nth-child(even) { background: rgba(255,255,255,0.02); }
      `}</style>
    </div>
  );
}
