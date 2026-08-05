import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useChatStore } from '../../stores/chat';
import { useDebouncedValue } from '../../hooks/useDebounce';
import { searchDataSources } from '../../services/api';
import type { DataSourceSearchResult } from '../../types';
import { X, Search } from 'lucide-react';
import { Badge } from '../ui/badge';

interface DataSourceSelectorProps {
  isOpen: boolean;
}

export function DataSourceSelector({ isOpen }: DataSourceSelectorProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<DataSourceSearchResult[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const messages = useChatStore((s) => s.messages);
  const addDataSource = useChatStore((s) => s.addDataSource);
  const removeDataSource = useChatStore((s) => s.removeDataSource);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) setIsDropdownOpen(false);
    };
    if (isDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isDropdownOpen]);

  useEffect(() => {
    if (!isOpen) return;
    inputRef.current?.focus();
    setIsDropdownOpen(true);
  }, [isOpen]);

  const debouncedQuery = useDebouncedValue(query, 300);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      setIsLoading(false);
      return;
    }

    let ignore = false;
    setIsLoading(true);
    setIsDropdownOpen(true);

    (async () => {
      try {
        const sources = await searchDataSources(debouncedQuery);
        if (!ignore) setResults(sources.slice(0, 10));
      } catch (err) {
        console.error('Failed to search data sources:', err);
        if (!ignore) setResults([]);
      } finally {
        if (!ignore) setIsLoading(false);
      }
    })();

    return () => { ignore = true; };
  }, [debouncedQuery]);

  if (!isOpen) return null;

  const dataSourceHistory = messages.flatMap((m) => m.dataSources ?? []);
  const uniqueDataSources = dataSourceHistory.filter(
    (ds, i) => dataSourceHistory.findIndex((d) => d.id === ds.id) === i,
  );
  const isShowingSuggestions = !debouncedQuery.trim();
  const visibleDataSources: DataSourceSearchResult[] = isShowingSuggestions ? uniqueDataSources : results;

  const handleSelect = (dataSource: DataSourceSearchResult) => {
    addDataSource({ id: dataSource.id, name: dataSource.name });
    setQuery('');
    setResults([]);
    setIsDropdownOpen(false);
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
      <div className={`flex items-center gap-2 px-3 py-2 bg-background border rounded-lg transition-colors ${isDropdownOpen ? 'border-primary' : 'border-border'}`}>
        <Search size={14} className={`shrink-0 transition-colors ${isDropdownOpen ? 'text-primary' : 'text-muted-foreground'}`} />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setIsDropdownOpen(true)}
          placeholder={t('chat.dataSource.searchPlaceholder')}
          className="flex-1 text-[13px] bg-transparent"
        />
      </div>

      {/* Dropdown results */}
      {isDropdownOpen && (isLoading || visibleDataSources.length > 0 || !isShowingSuggestions) && (
        <div className="absolute bottom-full start-0 end-0 mb-1 max-h-60 overflow-y-auto bg-popover border border-border rounded-lg shadow-[var(--shadow-md)] z-[1000]">
          {isLoading ? (
            <div className="p-3 text-center text-[13px] text-muted-foreground">Searching...</div>
          ) : visibleDataSources.length === 0 ? (
            <div className="p-3 text-center text-[13px] text-muted-foreground">No data sources found</div>
          ) : (
            visibleDataSources.map((dataSource) => {
              const alreadySelected = selectedIds.has(dataSource.id);
              return (
                <button
                  key={dataSource.id}
                  onClick={() => !alreadySelected && handleSelect(dataSource)}
                  disabled={alreadySelected}
                  className={`w-full px-3 py-2.5 text-left border-b border-border transition-colors ${
                    alreadySelected ? 'opacity-50 cursor-default' : 'cursor-pointer hover:bg-[color-mix(in_srgb,var(--primary)_8%,transparent)]'
                  }`}
                >
                  <div className="text-[13px] font-medium mb-0.5">
                    {dataSource.name}
                    {alreadySelected && <span className="text-muted-foreground font-normal"> (selected)</span>}
                  </div>
                  {isShowingSuggestions ? (
                    <div className="text-xs text-muted-foreground">{t('chat.dataSource.usedInProject')}</div>
                  ) : dataSource.description ? (
                    <div className="text-xs text-muted-foreground truncate">{dataSource.description}</div>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
