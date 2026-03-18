import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { ArrowUp, Loader2 } from 'lucide-react';
import { searchPackages } from '../../services/api';
import type { PackageSearchRecord } from '../../types';

export function PromptInput() {
  const [value, setValue] = useState('');
  const [packageQuery, setPackageQuery] = useState('');
  const [packageResults, setPackageResults] = useState<Pick<PackageSearchRecord, 'Id' | 'Name'>[]>([]);
  const [packageLoading, setPackageLoading] = useState(false);
  const [focused, setFocused] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const selectedPackage = useChatStore((s) => s.selectedPackage);
  const setSelectedPackage = useChatStore((s) => s.setSelectedPackage);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
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
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isBusy = isStreaming || (agentPhase !== 'idle' && agentPhase !== 'awaiting_approval' && agentPhase !== 'complete');
  const disabled = isBusy || !sessionId;

  const trimmedPackageQuery = useMemo(() => packageQuery.trim(), [packageQuery]);

  useEffect(() => {
    if (!sessionId || disabled) {
      setPackageResults([]);
      setPackageLoading(false);
      return;
    }

    if (!trimmedPackageQuery) {
      setPackageResults([]);
      setPackageLoading(false);
      return;
    }

    const handle = window.setTimeout(async () => {
      setPackageLoading(true);
      try {
        const results = await searchPackages(trimmedPackageQuery);
        const simplified = Array.isArray(results)
          ? results
              .filter((r) => r && typeof r.Id === 'number' && typeof r.Name === 'string')
              .map((r) => ({ Id: r.Id, Name: r.Name }))
          : [];
        setPackageResults(simplified);
      } catch {
        setPackageResults([]);
      } finally {
        setPackageLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(handle);
  }, [sessionId, disabled, trimmedPackageQuery]);
  const canSend = !!value.trim() && !disabled;

  const placeholder = !sessionId
    ? 'Select a project first'
    : agentPhase === 'awaiting_approval'
      ? 'Review the plan above, then accept, modify, or reject'
      : isBusy
        ? 'AI is working...'
        : 'Describe what you want to build...';

  const busyLabel =
    agentPhase === 'classifying' ? 'Analyzing' :
    agentPhase === 'designing' ? 'Designing' :
    agentPhase === 'planning' ? 'Planning' :
    agentPhase === 'executing' ? 'Building' :
    'Thinking';

  return (
    <div style={{
      padding: '10px 14px',
      borderTop: '1px solid var(--border)',
      background: 'var(--surface)',
      flexShrink: 0,
    }}>
      <div style={{ marginBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Package</div>
            <input
              value={packageQuery}
              onChange={(e) => {
                setPackageQuery(e.target.value);
                if (selectedPackage) setSelectedPackage(null);
              }}
              disabled={disabled}
              placeholder="Type package id (e.g. 3, 4, 572903)…"
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '10px',
                background: 'var(--bg)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                fontSize: '13px',
                opacity: disabled ? 0.6 : 1,
              }}
            />
          </div>
          {selectedPackage && (
            <button
              type="button"
              onClick={() => {
                setSelectedPackage(null);
                setPackageQuery('');
                setPackageResults([]);
              }}
              disabled={disabled}
              style={{
                padding: '8px 10px',
                borderRadius: '999px',
                border: '1px solid var(--border)',
                background: 'rgba(76, 167, 255, 0.12)',
                color: 'var(--text)',
                fontSize: '12px',
                cursor: disabled ? 'default' : 'pointer',
                whiteSpace: 'nowrap',
              }}
              title="Clear selected package"
            >
              {selectedPackage.Name} (#{selectedPackage.Id}) ×
            </button>
          )}
        </div>

        {!disabled && !!trimmedPackageQuery && !selectedPackage && (
          <div style={{
            marginTop: '6px',
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: '10px',
            overflow: 'hidden',
          }}>
            {packageLoading && (
              <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--text-dim)' }}>
                Searching…
              </div>
            )}
            {!packageLoading && packageResults.length === 0 && (
              <div style={{ padding: '8px 10px', fontSize: '12px', color: 'var(--text-dim)' }}>
                No package found (will show [] like FLAPI).
              </div>
            )}
            {!packageLoading && packageResults.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {packageResults.slice(0, 6).map((pkg) => (
                  <button
                    key={pkg.Id}
                    type="button"
                    onClick={() => {
                      setSelectedPackage(pkg);
                      setPackageQuery(String(pkg.Id));
                      setPackageResults([]);
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      border: 'none',
                      borderTop: '1px solid rgba(255,255,255,0.06)',
                      background: 'transparent',
                      color: 'var(--text)',
                      cursor: 'pointer',
                      fontSize: '13px',
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{pkg.Name}</div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)' }}>Id: {pkg.Id}</div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {isBusy && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '6px',
          fontSize: '12px',
          color: 'var(--accent)',
          marginBottom: '8px',
        }}>
          <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} />
          <span>{busyLabel}...</span>
        </div>
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '8px',
          background: 'var(--bg)',
          border: `1px solid ${focused && !disabled ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: '12px',
          padding: '4px 4px 4px 14px',
          transition: 'border-color 0.15s, box-shadow 0.15s',
          boxShadow: focused && !disabled
            ? '0 0 0 2px color-mix(in srgb, var(--accent) 12%, transparent)'
            : '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          style={{
            flex: 1,
            resize: 'none',
            fontSize: '14px',
            lineHeight: '1.5',
            maxHeight: '200px',
            padding: '6px 0',
            opacity: disabled ? 0.5 : 1,
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={!canSend}
          style={{
            width: '32px',
            height: '32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '8px',
            background: canSend ? 'var(--accent)' : 'var(--border)',
            color: canSend ? '#fff' : 'var(--text-dim)',
            opacity: canSend ? 1 : 0.4,
            flexShrink: 0,
            transition: 'background 0.15s, opacity 0.15s',
            cursor: canSend ? 'pointer' : 'default',
          }}
          title="Send message"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  );
}
