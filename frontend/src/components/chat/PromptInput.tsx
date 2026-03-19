import { useState, useRef, useCallback, useEffect } from 'react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { ArrowUp, Loader2, Database, X } from 'lucide-react';
import { CaseSelector } from './CaseSelector';
import { ModelSelector } from './ModelSelector';
import { Badge } from '../ui/badge';

export function PromptInput() {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [showCaseSelector, setShowCaseSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const selectedCases = useChatStore((s) => s.selectedCases);
  const removeCase = useChatStore((s) => s.removeCase);
  const sessionId = useSessionStore((s) => s.sessionId);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || !sessionId) return;
    sendMessage(trimmed);
    setValue('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isBusy = isStreaming || (agentPhase !== 'idle' && agentPhase !== 'awaiting_approval' && agentPhase !== 'complete');
  const disabled = isBusy || !sessionId;
  const canSend = !!value.trim() && !disabled;

  // Global keyboard shortcut: Cmd+K or / to focus
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
      if (e.key === '/' && document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const placeholder = !sessionId
    ? 'Select a project first'
    : agentPhase === 'awaiting_approval'
      ? 'Review the plan above, then accept, modify, or reject'
      : isBusy
        ? 'AI is working...'
        : 'Describe what you want to build...';

  const busyLabel =
    agentPhase === 'classifying' ? 'Analyzing' :
    agentPhase === 'fetching_cases' ? 'Fetching case data' :
    agentPhase === 'designing' ? 'Designing' :
    agentPhase === 'planning' ? 'Planning' :
    agentPhase === 'executing' ? 'Building' :
    'Thinking';

  return (
    <div className="px-4 py-3 border-t border-border bg-surface shrink-0">
      {/* Case selector */}
      {!isBusy && sessionId && showCaseSelector && (
        <div className="mb-2.5 relative">
          <CaseSelector isOpen={showCaseSelector} />
        </div>
      )}

      {/* Selected case badges */}
      {!showCaseSelector && selectedCases.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selectedCases.map((c) => (
            <Badge key={c.id} variant="accent" className="gap-1">
              <span className="font-medium">{c.name}</span>
              <button
                onClick={() => removeCase(c.id)}
                className="flex items-center justify-center w-4 h-4 rounded-sm hover:bg-primary/20"
                title="Remove case"
              >
                <X size={12} />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Busy indicator */}
      {isBusy && (
        <div className="flex items-center justify-center gap-1.5 text-xs text-primary mb-2">
          <Loader2 size={13} className="animate-spin" />
          <span>{busyLabel}...</span>
        </div>
      )}

      {/* Input row */}
      <div
        className={`flex items-end gap-2 bg-surface rounded-xl px-3.5 py-2 transition-all duration-200 ${
          focused && !disabled
            ? 'border border-primary/60 shadow-[0_0_0_3px_color-mix(in_srgb,var(--primary)_8%,transparent),0_2px_8px_color-mix(in_srgb,var(--primary)_6%,transparent)]'
            : 'border border-border shadow-[var(--shadow-sm)]'
        }`}
      >
        {/* Case selector toggle */}
        {!isBusy && sessionId && (
          <button
            onClick={() => setShowCaseSelector((v) => !v)}
            className={`relative w-8 h-8 flex items-center justify-center rounded-lg shrink-0 transition-colors ${
              showCaseSelector ? 'bg-primary/15' : ''
            } ${selectedCases.length > 0 ? 'text-primary' : 'text-muted-foreground'}`}
            title={showCaseSelector ? 'Hide case selector' : 'Attach cases'}
          >
            <Database size={16} />
            {selectedCases.length > 0 && (
              <span className="absolute top-0.5 right-0.5 w-3.5 h-3.5 rounded-full bg-primary text-text-on-accent text-[10px] font-bold flex items-center justify-center leading-none">
                {selectedCases.length}
              </span>
            )}
          </button>
        )}

        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => { setValue(e.target.value); adjustHeight(); }}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none text-[15px] leading-normal max-h-[200px] py-2 bg-transparent disabled:opacity-50"
        />

        <button
          onClick={handleSubmit}
          disabled={!canSend}
          className={`w-[34px] h-[34px] flex items-center justify-center rounded-xl shrink-0 transition-all duration-150 ${
            canSend
              ? 'bg-primary text-text-on-accent cursor-pointer hover:scale-105 hover:shadow-[0_0_12px_color-mix(in_srgb,var(--primary)_40%,transparent)] active:scale-95'
              : 'bg-border text-muted-foreground opacity-40 cursor-default'
          }`}
          title="Send message"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
      <div className="flex items-center justify-between mt-1.5 px-1">
        <div className="flex items-center gap-2">
          <ModelSelector />
          {selectedCases.length > 0 && (
            <span className="text-[10px] text-muted-foreground/50">
              {selectedCases.length} case{selectedCases.length > 1 ? 's' : ''} attached
            </span>
          )}
        </div>
        <span className="text-[11px] text-muted-foreground/60">
          <kbd className="px-1 py-0.5 rounded bg-muted text-muted-foreground/60 text-[10px] font-mono">Enter</kbd> send
          <span className="mx-1">·</span>
          <kbd className="px-1 py-0.5 rounded bg-muted text-muted-foreground/60 text-[10px] font-mono">Shift+Enter</kbd> new line
        </span>
      </div>
    </div>
  );
}
