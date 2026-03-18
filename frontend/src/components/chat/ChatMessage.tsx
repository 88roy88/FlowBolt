import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { FileText, TerminalSquare, Sparkles, CheckCircle2, XCircle, ArrowRight, Check, X, Package, AlertTriangle, ChevronDown, ChevronRight, Loader2, Search, Wrench, Save, TestTube, RefreshCw } from 'lucide-react';
import type { Message, PlanOverview, ExecutionTask, ProjectSummary, FixStep } from '../../types';

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
        {isUser && message.package && (
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
            <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>Package</span>
            <span style={{ fontWeight: 600 }}>{message.package.name}</span>
            <span style={{ color: 'var(--text-dim)' }}>#{message.package.id}</span>
          </div>
        )}
        {isUser ? (
          <p style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
        ) : (
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <ReactMarkdown
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
      `}</style>
    </div>
  );
}
