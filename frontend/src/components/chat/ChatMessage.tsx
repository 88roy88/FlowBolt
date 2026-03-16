import ReactMarkdown from 'react-markdown';
import { FileText, TerminalSquare } from 'lucide-react';
import type { Message } from '../../types';

interface ChatMessageProps {
  message: Message;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const isUser = message.role === 'user';

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
