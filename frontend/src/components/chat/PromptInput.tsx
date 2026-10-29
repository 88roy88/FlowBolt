import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chat';
import { isAwaitingPlanApproval, isAwaitingInterview } from '../../stores/chatAgentState';
import { useSessionStore } from '../../stores/session';
import { LOCK_MESSAGES, useWorkspaceLock } from '../../stores/workspaceLock';
import { ArrowUp, CirclePlus, Loader2, X } from 'lucide-react';
import { DataSourceSelector } from './DataSourceSelector';
import { ModelSelector } from './ModelSelector';
import { ModeSelector } from './ModeSelector';
import { Badge } from '../ui/badge';
import { startProjectFromPrompt } from '../../utils/newProject';
import type { AgentPhase } from '../../types';

const PHASE_LABEL_KEYS: Partial<Record<AgentPhase, string>> = {
  fetching_data_sources: 'chat.phase.fetchingDataSources',
  interviewing: 'chat.phase.interviewing',
  designing: 'chat.phase.designing',
  planning: 'chat.phase.planning',
  executing: 'chat.phase.building',
  fixing: 'chat.phase.fixing',
  exploring: 'chat.phase.exploring',
};

export function PromptInput() {
  const { t } = useTranslation();
  const [focused, setFocused] = useState(false);
  const [showDsSelector, setShowDsSelector] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const value = useChatStore((s) => s.draft);
  const setValue = useChatStore((s) => s.setDraft);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const awaitingPlan = useChatStore(isAwaitingPlanApproval);
  const awaitingInterview = useChatStore(isAwaitingInterview);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const removeDataSource = useChatStore((s) => s.removeDataSource);
  const projectId = useSessionStore((s) => s.projectId);
  const isCreating = useSessionStore((s) => s.isCreating);
  const canCreate = useSessionStore((s) => !!(s.userStatus?.is_platform_user || s.userStatus?.is_admin));
  const { lock, agentBusy } = useWorkspaceLock();
  const inputBlocked = lock !== null || awaitingPlan || awaitingInterview || isCreating;
  // No project open: submitting starts a new one, if the user may create projects
  const startsProject = !projectId && canCreate;

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }, [value]);

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || inputBlocked) return;
    if (projectId) sendMessage(trimmed);
    else if (startsProject) void startProjectFromPrompt(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const disabled = inputBlocked || (!projectId && !startsProject);
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
    if (isCreating) return t('chat.placeholder.creatingProject');
    if (!projectId && !startsProject) return t('chat.placeholder.selectProject');
    if (awaitingPlan) return t('chat.placeholder.reviewPlan');
    if (awaitingInterview) return t('chat.placeholder.reviewInterview');
    if (lock) return t(LOCK_MESSAGES[lock]);
    return t('chat.placeholder.default');
  };
  const placeholder = placeholderText();

  const busyLabel = t(PHASE_LABEL_KEYS[agentPhase] ?? 'chat.phase.thinking');

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
      ) : agentBusy ? (
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
          onChange={(e) => setValue(e.target.value)}
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
          {(projectId || startsProject) && (
            <button
              onClick={() => setShowDsSelector((v) => !v)}
              disabled={disabled}
              className={`relative w-7 h-7 flex items-center justify-center rounded-full shrink-0 transition-colors disabled:opacity-40 disabled:cursor-default ${
                dsOpen ? 'bg-primary/15' : 'enabled:hover:bg-muted/50'
              } ${selectedDataSources.length > 0 ? 'text-primary' : 'text-muted-foreground'}`}
              title={dsOpen ? 'Hide data source selector' : 'Attach data sources'}
            >
              <CirclePlus size={18} />
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
