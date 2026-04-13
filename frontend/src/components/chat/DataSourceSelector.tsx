import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chat';
import { searchDataSources } from '../../services/api';
import type { DataSourceSearchRecord } from '../../types';
import { X, Search } from 'lucide-react';
import { Badge } from '../ui/badge';

interface DataSourceSelectorProps {
  isOpen: boolean;
}

export function DataSourceSelector({ isOpen }: DataSourceSelectorProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DataSourceSearchRecord[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const addDataSource = useChatStore((s) => s.addDataSource);
  const removeDataSource = useChatStore((s) => s.removeDataSource);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) setShowDropdown(false);
    };
    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSearch = (searchQuery: string) => {
    setQuery(searchQuery);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!searchQuery.trim()) {
      setResults([]);
      setShowDropdown(false);
      return;
    }
    setIsLoading(true);
    setShowDropdown(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const sources = await searchDataSources(searchQuery);
        setResults(sources.slice(0, 10));
      } catch (err) {
        console.error('Failed to search data sources:', err);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);
  };

  const handleSelect = (pkg: DataSourceSearchRecord) => {
    addDataSource({ id: pkg.Id, name: pkg.Name });
    setQuery('');
    setResults([]);
    setShowDropdown(false);
  };

  const selectedIds = new Set(selectedDataSources.map((c) => c.id));

  return (
    <div ref={dropdownRef} className="relative">
      {/* Selected data source badges */}
      {selectedDataSources.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selectedDataSources.map((c) => (
            <Badge key={c.id} variant="accent" className="gap-1">
              <span className="font-medium">{c.name}</span>
              <button onClick={() => removeDataSource(c.id)} className="flex items-center justify-center w-4 h-4 rounded-sm hover:bg-primary/20" title={t('chat.dataSource.removeDataSource')}>
                <X size={12} />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Search input */}
      <div className={`flex items-center gap-2 px-3 py-2 bg-background border rounded-lg transition-colors ${showDropdown ? 'border-primary' : 'border-border'}`}>
        <Search size={14} className="text-muted-foreground shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
          onFocus={() => { if (results.length > 0) setShowDropdown(true); }}
          placeholder={t('chat.dataSource.searchPlaceholder')}
          className="flex-1 text-[13px] bg-transparent"
        />
      </div>

      {/* Dropdown results */}
      {showDropdown && (
        <div className="absolute bottom-full start-0 end-0 mb-1 max-h-60 overflow-y-auto bg-popover border border-border rounded-lg shadow-[var(--shadow-md)] z-[1000]">
          {isLoading ? (
            <div className="p-3 text-center text-[13px] text-muted-foreground">Searching...</div>
          ) : results.length === 0 ? (
            <div className="p-3 text-center text-[13px] text-muted-foreground">No data sources found</div>
          ) : (
            results.map((pkg) => {
              const alreadySelected = selectedIds.has(pkg.Id);
              return (
                <button
                  key={pkg.Id}
                  onClick={() => !alreadySelected && handleSelect(pkg)}
                  disabled={alreadySelected}
                  className={`w-full px-3 py-2.5 text-left border-b border-border transition-colors ${
                    alreadySelected ? 'opacity-50 cursor-default' : 'cursor-pointer hover:bg-[color-mix(in_srgb,var(--primary)_8%,transparent)]'
                  }`}
                >
                  <div className="text-[13px] font-medium mb-0.5">
                    {pkg.Name}
                    {alreadySelected && <span className="text-muted-foreground font-normal"> (selected)</span>}
                  </div>
                  {pkg.Description && (
                    <div className="text-xs text-muted-foreground truncate">{pkg.Description}</div>
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
