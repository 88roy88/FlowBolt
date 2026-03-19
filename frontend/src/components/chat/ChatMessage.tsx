import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, TerminalSquare } from 'lucide-react';
import type { Message } from '../../types';
import {
  CasesFetchedCard,
  DesignCompleteCard,
  PlanOverviewCard,
  TaskProgressCard,
  ProjectSummaryCard,
  ErrorFixRequestCard,
  FixProgressCard,
  FollowUpProgress,
} from './cards';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

function AgentCardRenderer({ message }: { message: Message }) {
  const card = message.agentCard!;

  switch (card.type) {
    case 'cases_fetched':
      return <CasesFetchedCard cases={card.cases} />;
    case 'package_fetched':
      return <CasesFetchedCard cases={[{
        packageId: card.packageId,
        packageName: card.packageName,
        dataSchema: card.dataSchema,
        relevantFields: card.relevantFields,
      }]} />;
    case 'design_complete':
      return <DesignCompleteCard architecture={card.architecture} ux={card.ux} />;
    case 'plan_overview':
      return <PlanOverviewCard overview={card.overview} accepted={card.accepted} />;
    case 'task_progress':
      return <TaskProgressCard tasks={card.tasks} />;
    case 'project_summary':
      return <ProjectSummaryCard summary={card.summary} />;
    case 'error_fix_request':
      return <ErrorFixRequestCard
        errorMessage={card.errorMessage}
        errorFile={card.errorFile}
        errorLine={card.errorLine}
        errorStack={card.errorStack}
      />;
    case 'fix_progress':
      return <FixProgressCard steps={card.steps} content={message.content} />;
    case 'followup_progress':
      return <FollowUpProgress
        steps={card.steps}
        answer={card.answer}
        filesChanged={card.filesChanged}
        diffs={card.diffs}
      />;
    default:
      return null;
  }
}

function CaseBadges({ cases }: { cases: { id: number; name: string }[] }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: 6 }}>
      {cases.map((c) => (
        <div key={c.id} style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '3px 8px',
          borderRadius: 999,
          background: 'var(--accent-bg)',
          border: '1px solid var(--accent-border)',
          color: 'var(--text)',
          fontSize: 12,
        }}>
          <span style={{ color: 'var(--text-dim)', fontWeight: 600 }}>Case</span>
          <span style={{ fontWeight: 600 }}>{c.name}</span>
          <span style={{ color: 'var(--text-dim)' }}>#{c.id}</span>
        </div>
      ))}
    </div>
  );
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user';

  if (!message.content && !message.agentCard && !message.actions?.length && !isStreaming) {
    return null;
  }

  // Agent card messages
  if (message.agentCard) {
    return (
      <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
        <div style={{ maxWidth: '85%' }}>
          <AgentCardRenderer message={message} />
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
        border: '1px solid var(--border)',
        fontSize: '14px',
        lineHeight: '1.6',
      }}>
        {isUser && message.cases && message.cases.length > 0 && (
          <CaseBadges cases={message.cases} />
        )}
        {/* Backward compat for old single-package messages */}
        {isUser && !message.cases && message.package && (
          <CaseBadges cases={[{ id: message.package.id, name: message.package.name }]} />
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
        .markdown-content tr:nth-child(even) { background: var(--table-stripe); }
      `}</style>
    </div>
  );
}
