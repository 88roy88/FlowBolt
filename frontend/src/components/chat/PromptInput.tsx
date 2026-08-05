import { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chat';
import { isAgentAlive, isAwaitingPlanApproval, isAwaitingInterview } from '../../stores/chatAgentState';
import { useSessionStore } from '../../stores/session';
import { ArrowUp, Loader2, Database, X } from 'lucide-react';
import { DataSourceSelector } from './DataSourceSelector';
import { ModelSelector } from './ModelSelector';
import { ModeSelector } from './ModeSelector';
import { Badge } from '../ui/badge';

import { WRITE_ROLES } from '../../types';

export function PromptInput() {
  const { t } = useTranslation();
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const [showDsSelector, setShowDsSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const agentAlive = useChatStore(isAgentAlive);
  const awaitingPlan = useChatStore(isAwaitingPlanApproval);
  const awaitingInterview = useChatStore(isAwaitingInterview);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const removeDataSource = useChatStore((s) => s.removeDataSource);
  const projectId = useSessionStore((s) => s.projectId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const projectRole = currentProject?.role;
  const canWrite = !projectRole || WRITE_ROLES.has(projectRole);
  const inputBlocked = agentAlive || awaitingPlan || awaitingInterview || !canWrite;

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 200) + 'px';
    }
  }, []);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || inputBlocked || !projectId) return;
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

  const disabled = inputBlocked || !projectId;
  const canSend = !!value.trim() && !disabled;
  const dsOpen = showDsSelector && !disabled;

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

  const placeholderText = () => {
    if (!projectId) return t('chat.placeholder.selectProject');
    if (!canWrite) return t('chat.placeholder.readOnly');
    if (awaitingPlan) return t('chat.placeholder.reviewPlan');
    if (awaitingInterview) return t('chat.placeholder.reviewInterview');
    if (inputBlocked) return t('chat.placeholder.working');
    return t('chat.placeholder.default');
  };
  const placeholder = placeholderText();

  const busyLabel =
    agentPhase === 'fetching_data_sources' ? t('chat.phase.fetchingDataSources') :
    agentPhase === 'interviewing' ? t('chat.phase.interviewing') :
    agentPhase === 'designing' ? t('chat.phase.designing') :
    agentPhase === 'planning' ? t('chat.phase.planning') :
    agentPhase === 'executing' ? t('chat.phase.building') :
    agentPhase === 'fixing' ? t('chat.phase.fixing') :
    agentPhase === 'exploring' ? t('chat.phase.exploring') :
    t('chat.phase.thinking');

  return (
    <div className="px-4 pt-2 pb-4 shrink-0">
      {/* Data source selector */}
      {dsOpen && (
        <div className="mb-2.5 relative">
          <DataSourceSelector isOpen={dsOpen} />
        </div>
      )}

      {/* Busy/awaiting indicator */}
      {awaitingPlan ? (
        <div className="flex items-center justify-center gap-1.5 text-xs text-warning mb-2">
          <span>↑ {t('chat.placeholder.reviewPlan')}</span>
        </div>
      ) : agentAlive ? (
        <div className="flex items-center justify-center gap-1.5 text-xs text-primary mb-2">
          <Loader2 size={13} className="animate-spin" />
          <span>{busyLabel}...</span>
        </div>
      ) : null}

      <div
        className={`flex flex-col gap-2 bg-surface rounded-2xl p-2.5 transition-all duration-200 ${
          focused && !disabled
            ? 'border border-primary/60 shadow-[0_0_0_3px_color-mix(in_srgb,var(--primary)_8%,transparent),0_2px_8px_color-mix(in_srgb,var(--primary)_6%,transparent)]'
            : 'border border-border shadow-[var(--shadow-md)]'
        }`}
      >
        {/* Selected data source badges */}
        {!dsOpen && selectedDataSources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1">
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
          className="w-full resize-none text-[15px] leading-normal max-h-[200px] px-1.5 pt-1.5 bg-transparent disabled:opacity-50"
        />

        <div className="flex items-center gap-2">
          {/* Data source selector toggle */}
          {projectId && (
            <button
              onClick={() => setShowDsSelector((v) => !v)}
              disabled={disabled}
              className={`relative w-7 h-7 flex items-center justify-center rounded-full shrink-0 transition-colors disabled:opacity-40 disabled:cursor-default ${
                dsOpen ? 'bg-primary/15' : 'enabled:hover:bg-muted/50'
              } ${selectedDataSources.length > 0 ? 'text-primary' : 'text-muted-foreground'}`}
              title={dsOpen ? 'Hide data source selector' : 'Attach data sources'}
            >
              <Database size={15} />
              {selectedDataSources.length > 0 && (
                <span className="absolute -top-0.5 -end-0.5 w-3.5 h-3.5 rounded-full bg-primary text-text-on-accent text-[10px] font-bold flex items-center justify-center leading-none">
                  {selectedDataSources.length}
                </span>
              )}
            </button>
          )}

          <div className="flex items-center gap-1 ms-auto min-w-0">
            <ModeSelector />
            <ModelSelector />
          </div>

          <button
            onClick={handleSubmit}
            disabled={!canSend}
            data-testid="send-button"
            className={`w-8 h-8 ms-2 flex items-center justify-center rounded-full shrink-0 transition-all duration-150 ${
              canSend
                ? 'bg-primary text-text-on-accent cursor-pointer hover:scale-105 hover:shadow-[0_0_12px_color-mix(in_srgb,var(--primary)_40%,transparent)] active:scale-95'
                : 'bg-muted text-muted-foreground opacity-50 cursor-default'
            }`}
            title={t('common.sendMessage')}
          >
            <ArrowUp size={16} strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  );
}
