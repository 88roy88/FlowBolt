import { useEffect, useRef, useMemo, useState } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import type { AIModel } from '../../types';

export function ModelSelector() {
  const { models, selectedModel, setSelectedModel, loadModels } = useChatStore();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    loadModels();
  }, [loadModels]);

  const grouped = useMemo(() => {
    const groups: Record<string, AIModel[]> = {};
    for (const model of models) {
      if (!groups[model.provider]) groups[model.provider] = [];
      groups[model.provider].push(model);
    }
    return groups;
  }, [models]);

  const current = models.find((m) => m.id === selectedModel) ?? models[0];

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: '999px',
          color: 'var(--text)',
          fontSize: '12px',
          cursor: 'pointer',
          maxWidth: '260px',
        }}
        title={current?.id ?? 'Loading models…'}
      >
        <span style={{ fontWeight: 500, color: 'var(--text-dim)' }}>Model</span>
        <span
          style={{
            flex: 1,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            textAlign: 'left',
          }}
        >
          {current?.name ?? current?.id ?? 'Loading models…'}
        </span>
        <ChevronDown size={14} style={{ flexShrink: 0, opacity: 0.7 }} />
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: '110%',
            right: 0,
            marginTop: '4px',
            minWidth: '260px',
            maxHeight: '320px',
            overflow: 'auto',
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            boxShadow: 'var(--shadow-lg)',
            zIndex: 40,
          }}
        >
          {Object.entries(grouped).map(([provider, providerModels]) => (
            <div key={provider}>
              <div
                style={{
                  padding: '6px 10px',
                  fontSize: '11px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--text-dim)',
                  borderBottom: '1px solid var(--dropdown-divider)',
                  background: 'var(--dropdown-header-bg)',
                }}
              >
                {provider}
              </div>
              {providerModels.map((m) => {
                const isActive = (selectedModel ?? current.id) === m.id;
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setSelectedModel(m.id);
                      setOpen(false);
                    }}
                    style={{
                      width: '100%',
                      padding: '6px 10px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      background: isActive ? 'var(--accent-bg-strong)' : 'transparent',
                      border: 'none',
                      borderBottom: '1px solid var(--dropdown-divider)',
                      color: 'var(--text)',
                      fontSize: '12px',
                      textAlign: 'left',
                      cursor: 'pointer',
                    }}
                  >
                    <Check
                      size={14}
                      style={{
                        opacity: isActive ? 1 : 0,
                        color: 'var(--accent)',
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {m.name}
                    </span>
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
