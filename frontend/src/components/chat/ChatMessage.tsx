import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useTranslation } from 'react-i18next';
import { FileText, TerminalSquare } from 'lucide-react';
import type { Message } from '../../types';
import { formatClock } from '../../utils/formatTime';
import { Badge } from '../ui/badge';
import {
  DataSourcesFetchedCard,
  DesignCompleteCard,
  PlanOverviewCard,
  TaskProgressCard,
  ProjectSummaryCard,
  ErrorFixRequestCard,
  FixProgressCard,
  FollowUpProgress,
  UserEditCard,
} from './cards';
import { VersionControl } from './VersionControl';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

function AgentCardRenderer({ message }: { message: Message }) {
  const card = message.agentCard!;

  switch (card.type) {
    case 'data_sources_fetched':
      return <DataSourcesFetchedCard dataSources={card.dataSources} />;
    case 'design_complete':
      return <DesignCompleteCard architecture={card.architecture} ux={card.ux} />;
    case 'plan_overview':
      return <PlanOverviewCard overview={card.overview} />;
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
    case 'user_edit':
      return <UserEditCard diffs={card.diffs} />;
    case 'fix_progress':
      return <FixProgressCard steps={card.steps} content={message.content} diffs={card.diffs} />;
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

function DataSourceBadges({ dataSources }: { dataSources: { id: number; name: string }[] }) {
  return (
    <div className="flex flex-wrap gap-1 mb-1.5">
      {dataSources.map((ds) => (
        <Badge key={ds.id} variant="accent">
          <span className="text-muted-foreground font-semibold">Data</span>
          <span className="font-semibold">{ds.name}</span>
          <span className="text-muted-foreground">#{ds.id}</span>
        </Badge>
      ))}
    </div>
  );
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const { i18n } = useTranslation();
  const isUser = message.role === 'user';

  if (!message.content && !message.agentCard && !message.actions?.length && !isStreaming) {
    return null;
  }

  const versionControl = message.version && (
    <div className="max-w-[85%] px-1">
      <VersionControl commit_sha={message.version} />
    </div>
  );

  const timestamp = !isStreaming && (
    <span className="px-1 text-[11px] text-muted-foreground/60 opacity-0 group-hover:opacity-100 transition-opacity">
      {formatClock(message.timestamp, i18n.language)}
    </span>
  );

  // Agent card messages
  if (message.agentCard) {
    return (
      <div className={`group flex flex-col w-full ${isUser ? 'items-end' : 'items-start'} animate-message-in`}>
        <AgentCardRenderer message={message} />
        {versionControl}
        {message.agentCard.type === 'error_fix_request' && timestamp}
      </div>
    );
  }

  return (
    <div className={`group flex flex-col w-full ${isUser ? 'items-end' : 'items-start'} animate-message-in`}>
      <div
        className={`min-w-0 max-w-[85%] overflow-hidden px-3.5 py-2.5 rounded-xl text-sm leading-relaxed ${
          isUser ? 'bg-user-bubble border border-primary/30' : 'bg-assistant-bubble border border-border'
        }`}
      >
        {isUser && message.dataSources && message.dataSources.length > 0 && (
          <DataSourceBadges dataSources={message.dataSources} />
        )}
        {isUser ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <div className="markdown-content break-words overflow-hidden">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ children, className, ...props }) {
                  const isInline = !className;
                  if (isInline) {
                    return (
                      <code className="bg-background px-1.5 py-0.5 rounded text-[13px] font-mono break-all" {...props}>
                        {children}
                      </code>
                    );
                  }
                  return (
                    <pre className="bg-background p-3 rounded-md overflow-x-auto text-[13px] font-mono my-2 max-w-full">
                      <code {...props}>{children}</code>
                    </pre>
                  );
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-primary ms-0.5 align-text-bottom animate-[blink_1s_step-end_infinite]" />
            )}
          </div>
        )}

        {/* Action indicators */}
        {message.actions && message.actions.length > 0 && (
          <div className="mt-2 flex flex-col gap-1">
            {message.actions.map((action, i) => (
              <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground px-2 py-1 bg-background rounded">
                {action.type === 'file' ? (
                  <>
                    <FileText size={14} className="text-primary shrink-0" />
                    <span className="truncate">{action.path}</span>
                  </>
                ) : (
                  <>
                    <TerminalSquare size={14} className="text-success shrink-0" />
                    <span className="truncate">{action.command}</span>
                  </>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {versionControl}
      {timestamp}
    </div>
  );
}
