import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../../stores/chat';
import { searchPackages } from '../../services/api';
import type { PackageSearchRecord } from '../../types';
import { X, Search } from 'lucide-react';

interface CaseSelectorProps {
  isOpen: boolean;
}

export function CaseSelector({ isOpen }: CaseSelectorProps) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PackageSearchRecord[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const selectedCases = useChatStore((s) => s.selectedCases);
  const addCase = useChatStore((s) => s.addCase);
  const removeCase = useChatStore((s) => s.removeCase);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery);
    if (!searchQuery.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }

    setIsLoading(true);
    setShowDropdown(true);
    try {
      const packages = await searchPackages(searchQuery);
      setResults(packages.slice(0, 10));
    } catch (err) {
      console.error('Failed to search cases:', err);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelect = (pkg: PackageSearchRecord) => {
    addCase({ id: pkg.Id, name: pkg.Name });
    setQuery('');
    setResults([]);
    setShowDropdown(false);
  };

  const selectedIds = new Set(selectedCases.map((c) => c.id));

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      {/* Selected case badges */}
      {selectedCases.length > 0 && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          marginBottom: '8px',
        }}>
          {selectedCases.map((c) => (
            <div
              key={c.id}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
                border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)',
                borderRadius: '6px',
                fontSize: '12px',
              }}
            >
              <span style={{ fontWeight: 500 }}>{c.name}</span>
              <button
                onClick={() => removeCase(c.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '16px',
                  height: '16px',
                  borderRadius: '3px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-dim)',
                  padding: 0,
                }}
                title="Remove case"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Search input */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        background: 'var(--bg)',
        border: `1px solid ${showDropdown ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: '8px',
        transition: 'border-color 0.15s',
      }}>
        <Search size={14} style={{ color: 'var(--text-dim)', flexShrink: 0 }} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => {
            if (results.length > 0) setShowDropdown(true);
          }}
          placeholder="Search cases (optional)"
          style={{
            flex: 1,
            fontSize: '13px',
            border: 'none',
            background: 'transparent',
            outline: 'none',
            color: 'var(--text)',
          }}
        />
      </div>

      {/* Dropdown results */}
      {showDropdown && (
        <div style={{
          position: 'absolute',
          bottom: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          maxHeight: '240px',
          overflowY: 'auto',
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          zIndex: 1000,
        }}>
          {isLoading ? (
            <div style={{
              padding: '12px',
              textAlign: 'center',
              fontSize: '13px',
              color: 'var(--text-dim)',
            }}>
              Searching...
            </div>
          ) : results.length === 0 ? (
            <div style={{
              padding: '12px',
              textAlign: 'center',
              fontSize: '13px',
              color: 'var(--text-dim)',
            }}>
              No cases found
            </div>
          ) : (
            results.map((pkg) => {
              const alreadySelected = selectedIds.has(pkg.Id);
              return (
                <button
                  key={pkg.Id}
                  onClick={() => !alreadySelected && handleSelect(pkg)}
                  disabled={alreadySelected}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    textAlign: 'left',
                    border: 'none',
                    background: 'transparent',
                    cursor: alreadySelected ? 'default' : 'pointer',
                    transition: 'background 0.15s',
                    borderBottom: '1px solid var(--border)',
                    opacity: alreadySelected ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!alreadySelected) {
                      e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 8%, transparent)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '2px' }}>
                    {pkg.Name}
                    {alreadySelected && <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}> (selected)</span>}
                  </div>
                  {pkg.Description && (
                    <div style={{
                      fontSize: '12px',
                      color: 'var(--text-dim)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}>
                      {pkg.Description}
                    </div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
