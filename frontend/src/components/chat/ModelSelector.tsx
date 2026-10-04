import { useEffect, useRef, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, Check } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { useClickOutside } from '../../hooks/useClickOutside';
import type { AIModel } from '../../types';

export function ModelSelector() {
  const { t } = useTranslation();
  const { models, selectedModel, setSelectedModel, loadModels } = useChatStore();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { loadModels(); }, [loadModels]);

  const grouped = useMemo(() => {
    const groups: Record<string, AIModel[]> = {};
    for (const model of models) {
      if (!groups[model.provider]) groups[model.provider] = [];
      groups[model.provider].push(model);
    }
    return groups;
  }, [models]);

  const current = models.find((m) => m.id === selectedModel) ?? models[0];

  // If the selected model is no longer available, sync the store to the fallback
  useEffect(() => {
    if (models.length === 0) return;
    if (!models.find((m) => m.id === selectedModel)) {
      setSelectedModel(models[0].id);
    }
  }, [models, selectedModel, setSelectedModel]);

  useClickOutside(dropdownRef, setOpen, open);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 h-7 px-2 rounded-full text-xs text-muted-foreground cursor-pointer hover:text-foreground hover:bg-muted/50 transition-colors"
        title={current?.name ?? current?.id ?? 'Loading models…'}
      >
        <span>{t('chat.model')}</span>
        <ChevronDown size={13} className="shrink-0 opacity-60" />
      </button>

      {open && (
        <div className="absolute bottom-full end-0 mb-1.5 w-[200px] max-h-80 overflow-auto bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] z-40">
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="px-2.5 py-1.5 text-[11px] uppercase tracking-wider text-muted-foreground border-b border-dropdown-divider bg-dropdown-header-bg">
                {provider}
              </div>
              {providerModels.map((m) => {
                const isActive = (selectedModel ?? current.id) === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => { setSelectedModel(m.id); setOpen(false); }}
                    className={`w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-left cursor-pointer border-b border-dropdown-divider ${
                      isActive ? 'bg-accent-bg-strong' : 'hover:bg-muted/50'
                    }`}
                  >
                    <Check size={14} className={`shrink-0 text-primary ${isActive ? 'opacity-100' : 'opacity-0'}`} />
                    <span className="flex-1 truncate">{m.name}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
