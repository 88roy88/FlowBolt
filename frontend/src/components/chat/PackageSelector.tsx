import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../../stores/chat';
import { searchPackages } from '../../services/api';
import type { PackageSearchRecord } from '../../types';
import { X, Search, Package } from 'lucide-react';

export function PackageSelector() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PackageSearchRecord[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const selectedPackage = useChatStore((s) => s.selectedPackage);
  const setSelectedPackage = useChatStore((s) => s.setSelectedPackage);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleSearch = async (searchQuery: string) => {
    setQuery(searchQuery);
    if (!searchQuery.trim()) {
      setResults([]);
      setIsOpen(false);
      return;
    }

    setIsLoading(true);
    setIsOpen(true);
    try {
      const packages = await searchPackages(searchQuery);
      setResults(packages.slice(0, 10));
    } catch (err) {
      console.error('Failed to search packages:', err);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelect = (pkg: PackageSearchRecord) => {
    setSelectedPackage({ id: pkg.Id, name: pkg.Name });
    setQuery('');
    setResults([]);
    setIsOpen(false);
  };

  const handleClear = () => {
    setSelectedPackage(null);
    setQuery('');
    setResults([]);
    setIsOpen(false);
  };

  if (selectedPackage) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        background: 'color-mix(in srgb, var(--accent) 10%, transparent)',
        border: '1px solid color-mix(in srgb, var(--accent) 30%, transparent)',
        borderRadius: '8px',
        fontSize: '13px',
      }}>
        <Package size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
        <span style={{ flex: 1, fontWeight: 500 }}>{selectedPackage.name}</span>
        <button
          onClick={handleClear}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '20px',
            height: '20px',
            borderRadius: '4px',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--text-dim)',
            transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 20%, transparent)';
            e.currentTarget.style.color = 'var(--text)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent';
            e.currentTarget.style.color = 'var(--text-dim)';
          }}
          title="Remove package"
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <div ref={dropdownRef} style={{ position: 'relative' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        background: 'var(--bg)',
        border: `1px solid ${isOpen ? 'var(--accent)' : 'var(--border)'}`,
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
            if (results.length > 0) setIsOpen(true);
          }}
          placeholder="Search packages (optional)"
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

      {isOpen && (
        <div style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
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
              No packages found
            </div>
          ) : (
            results.map((pkg) => (
              <button
                key={pkg.Id}
                onClick={() => handleSelect(pkg)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  textAlign: 'left',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  transition: 'background 0.15s',
                  borderBottom: '1px solid var(--border)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'color-mix(in srgb, var(--accent) 8%, transparent)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ fontSize: '13px', fontWeight: 500, marginBottom: '2px' }}>
                  {pkg.Name}
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
            ))
          )}
        </div>
      )}
    </div>
  );
}
