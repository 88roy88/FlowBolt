import { useEffect, useRef, useMemo, useState } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import type { AIModel } from '../../types';

export function ModelSelector() {
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

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={dropdownRef} className="relative">
      <button
        data-testid="model-selector-button"
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1 bg-background border border-border rounded-full text-xs cursor-pointer max-w-[260px]"
        title={current?.id ?? 'Loading models…'}
      >
        <span className="font-medium text-muted-foreground">Model</span>
        <span className="flex-1 truncate text-left">{current?.name ?? current?.id ?? 'Loading models…'}</span>
        <ChevronDown size={14} className="shrink-0 opacity-70" />
      </button>

      {open && (
        <div className="absolute bottom-full start-0 mb-1 min-w-[260px] max-h-80 overflow-auto bg-popover border border-border rounded-lg shadow-[var(--shadow-lg)] z-40">
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div className="px-2.5 py-1.5 text-[11px] uppercase tracking-wider text-muted-foreground border-b border-[var(--dropdown-divider)] bg-[var(--dropdown-header-bg)]">
                {provider}
              </div>
              {providerModels.map((m) => {
                const isActive = (selectedModel ?? current.id) === m.id;
                return (
                  <button
                    key={m.id}
                    data-testid={`model-option-${m.id}`}
                    type="button"
                    onClick={() => { setSelectedModel(m.id); setOpen(false); }}
                    className={`w-full flex items-center gap-2 px-2.5 py-1.5 text-xs text-left cursor-pointer border-b border-[var(--dropdown-divider)] ${
                      isActive ? 'bg-[var(--accent-bg-strong)]' : 'hover:bg-muted/50'
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
