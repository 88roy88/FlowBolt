import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Check } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { useClickOutside } from '../../hooks/useClickOutside';
import type { InterviewMode } from '../../types';

const MODES: InterviewMode[] = ['interview', 'build'];

export function ModeSelector() {
  const { t } = useTranslation();
  const interviewMode = useChatStore((s) => s.interviewMode);
  const setInterviewMode = useChatStore((s) => s.setInterviewMode);
  const buildCompleted = useChatStore((s) => s.buildCompleted);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useClickOutside(dropdownRef, setOpen, open);

  if (buildCompleted) return null;

  const label = (mode: InterviewMode) => (mode === 'interview' ? t('chat.interview.modePlan') : t('chat.interview.modeBuild'));
  const hint = (mode: InterviewMode) => (mode === 'interview' ? t('chat.interview.modePlanHint') : t('chat.interview.modeBuildHint'));

  return (
    <div ref={dropdownRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 h-7 px-2 rounded-full text-xs text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        title={hint(interviewMode)}
      >
        <span>{label(interviewMode)}</span>
        <ChevronDown size={13} className="shrink-0 opacity-60" />
      </button>

      {open && (
        <div className="absolute bottom-full end-0 mb-1.5 w-[200px] bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] overflow-hidden z-40">
          {MODES.map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => { setInterviewMode(mode); setOpen(false); }}
              className={`w-full flex items-start gap-2 px-2.5 py-2 text-start border-b border-dropdown-divider last:border-b-0 ${
                interviewMode === mode ? 'bg-accent-bg-strong' : 'hover:bg-muted/50'
              }`}
            >
              <Check size={14} className={`shrink-0 mt-0.5 text-primary ${interviewMode === mode ? 'opacity-100' : 'opacity-0'}`} />
              <span className="min-w-0">
                <span className="block text-xs font-medium">{label(mode)}</span>
                <span className="block text-[11px] leading-snug text-muted-foreground">{hint(mode)}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
