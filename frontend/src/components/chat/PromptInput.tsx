import { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { ArrowUp, Loader2, Database, X } from 'lucide-react';
import { DataSourceSelector } from './DataSourceSelector';
import { ModelSelector } from './ModelSelector';
import { Badge } from '../ui/badge';

export function PromptInput() {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [showDsSelector, setShowDsSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const removeDataSource = useChatStore((s) => s.removeDataSource);
  const projectId = useSessionStore((s) => s.projectId);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming || !projectId) return;
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

  const isBusy = isStreaming || (agentPhase !== 'idle' && agentPhase !== 'complete');
  const disabled = isBusy || !projectId;
  const canSend = !!value.trim() && !disabled;

  // Global keyboard shortcut: Cmd+K to focus chat
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const placeholder = !projectId
    ? t('chat.placeholder.selectProject')
    : agentPhase === 'awaiting_approval'
      ? t('chat.placeholder.reviewPlan')
      : isBusy
        ? t('chat.placeholder.working')
        : t('chat.placeholder.default');

  const busyLabel =
    agentPhase === 'classifying' ? t('chat.phase.analyzing') :
    agentPhase === 'fetching_data_sources' ? t('chat.phase.fetchingDataSources') :
    agentPhase === 'designing' ? t('chat.phase.designing') :
    agentPhase === 'planning' ? t('chat.phase.planning') :
    agentPhase === 'executing' ? t('chat.phase.building') :
    t('chat.phase.thinking');

  return (
    <div className="px-4 py-3 border-t border-border bg-surface shrink-0">
      {/* Data source selector */}
      {!isBusy && projectId && showDsSelector && (
        <div className="mb-2.5 relative">
          <DataSourceSelector isOpen={showDsSelector} />
        </div>
      )}

      {/* Selected data source badges */}
      {!showDsSelector && selectedDataSources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selectedDataSources.map((c) => (
            <Badge key={c.id} variant="accent" className="gap-1">
              <span className="font-medium">{c.name}</span>
              <button
                onClick={() => removeDataSource(c.id)}
                className="flex items-center justify-center w-4 h-4 rounded-sm hover:bg-primary/20"
                title={t('chat.dataSource.removeDataSource')}
              >
                <X size={12} />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Busy/awaiting indicator */}
      {agentPhase === 'awaiting_approval' ? (
        <div className="flex items-center justify-center gap-1.5 text-xs text-warning mb-2">
          <span>↑ {t('chat.placeholder.reviewPlan')}</span>
        </div>
      ) : isBusy ? (
        <div className="flex items-center justify-center gap-1.5 text-xs text-primary mb-2">
          <Loader2 size={13} className="animate-spin" />
          <span>{busyLabel}...</span>
        </div>
      ) : null}

      {/* Input row */}
      <div
        className={`flex items-end gap-2 bg-surface rounded-xl px-3.5 py-2 transition-all duration-200 ${
          focused && !disabled
            ? 'border border-primary/60 shadow-[0_0_0_3px_color-mix(in_srgb,var(--primary)_8%,transparent),0_2px_8px_color-mix(in_srgb,var(--primary)_6%,transparent)]'
            : 'border border-border shadow-[var(--shadow-sm)]'
        }`}
      >
        {/* Data source selector toggle */}
        {!isBusy && projectId && (
          <button
            onClick={() => setShowDsSelector((v) => !v)}
            className={`relative w-8 h-8 flex items-center justify-center rounded-lg shrink-0 transition-colors ${
              showDsSelector ? 'bg-primary/15' : ''
            } ${selectedDataSources.length > 0 ? 'text-primary' : 'text-muted-foreground'}`}
            title={showDsSelector ? 'Hide data source selector' : 'Attach data sources'}
          >
            <Database size={16} />
            {selectedDataSources.length > 0 && (
              <span className="absolute top-0.5 end-0.5 w-3.5 h-3.5 rounded-full bg-primary text-text-on-accent text-[10px] font-bold flex items-center justify-center leading-none">
                {selectedDataSources.length}
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
          data-testid="chat-input"
          className="flex-1 resize-none text-[15px] leading-normal max-h-[200px] py-1 bg-transparent disabled:opacity-50"
        />

        <button
          onClick={handleSubmit}
          disabled={!canSend}
          data-testid="send-button"
          className={`w-[34px] h-[34px] flex items-center justify-center rounded-xl shrink-0 transition-all duration-150 ${
            canSend
              ? 'bg-primary text-text-on-accent cursor-pointer hover:scale-105 hover:shadow-[0_0_12px_color-mix(in_srgb,var(--primary)_40%,transparent)] active:scale-95'
              : 'bg-border text-muted-foreground opacity-40 cursor-default'
          }`}
          title={t('common.sendMessage')}
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
      <div className="flex items-center justify-between mt-1.5 pt-1 px-1 gap-2">
        <div className="flex items-center gap-2 min-w-0 shrink-0">
          <ModelSelector />
          {selectedDataSources.length > 0 && (
            <span className="text-[10px] text-muted-foreground/50 hidden sm:inline">
              {selectedDataSources.length} data source{selectedDataSources.length > 1 ? 's' : ''} attached
            </span>
          )}
        </div>
        <span className="text-[11px] text-muted-foreground/60 hidden md:inline shrink-0">
          <kbd className="px-1 py-0.5 rounded bg-muted text-muted-foreground/60 text-[10px] font-mono">Enter</kbd> {t('chat.send')}
          <span className="mx-1">·</span>
          <kbd className="px-1 py-0.5 rounded bg-muted text-muted-foreground/60 text-[10px] font-mono">Shift+Enter</kbd> {t('chat.newLine')}
        </span>
      </div>
    </div>
  );
}
