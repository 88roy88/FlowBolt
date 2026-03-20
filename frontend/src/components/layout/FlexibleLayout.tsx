import { useState, useRef, useCallback, useEffect } from 'react';
import { MessageSquare, Code2, Eye } from 'lucide-react';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Preview } from '../preview/Preview';
import { useChatStore } from '../../stores/chat';

type PaneId = 'chat' | 'code' | 'preview';

const PANE_CONFIG: Record<PaneId, { icon: typeof MessageSquare; label: string }> = {
  chat: { icon: MessageSquare, label: 'Chat' },
  code: { icon: Code2, label: 'Code' },
  preview: { icon: Eye, label: 'Preview' },
};

const MIN_PANE_PCT = 20;

export function FlexibleLayout() {
  const [visiblePanes, setVisiblePanes] = useState<Set<PaneId>>(new Set(['chat', 'preview']));
  const [paneSizes, setPaneSizes] = useState<Record<PaneId, number>>({ chat: 50, code: 50, preview: 50 });
  const panesContainerRef = useRef<HTMLDivElement>(null);
  const agentPhase = useChatStore((s) => s.agentPhase);

  const togglePane = (pane: PaneId) => {
    setVisiblePanes(prev => {
      const next = new Set(prev);
      if (next.has(pane)) {
        if (next.size <= 1) return prev;
        next.delete(pane);
      } else {
        next.add(pane);
      }
      const equal = 100 / next.size;
      const newSizes = { ...paneSizes };
      for (const id of next) newSizes[id] = equal;
      setPaneSizes(newSizes);
      return next;
    });
  };

  const handlePaneResize = useCallback((leftPane: PaneId, rightPane: PaneId, delta: number) => {
    const container = panesContainerRef.current;
    if (!container) return;
    const totalWidth = container.getBoundingClientRect().width;
    if (totalWidth <= 0) return;
    const pctDelta = (delta / totalWidth) * 100;
    setPaneSizes(prev => {
      const sumBoth = prev[leftPane] + prev[rightPane];
      let newLeft = prev[leftPane] + pctDelta;
      let newRight = prev[rightPane] - pctDelta;
      if (newLeft < MIN_PANE_PCT) { newLeft = MIN_PANE_PCT; newRight = sumBoth - MIN_PANE_PCT; }
      if (newRight < MIN_PANE_PCT) { newRight = MIN_PANE_PCT; newLeft = sumBoth - MIN_PANE_PCT; }
      return { ...prev, [leftPane]: newLeft, [rightPane]: newRight };
    });
  }, []);

  useEffect(() => {
    if (agentPhase === 'executing' || agentPhase === 'complete') {
      setVisiblePanes(prev => new Set([...prev, 'preview']));
    }
  }, [agentPhase]);

  const visiblePaneList = (['chat', 'code', 'preview'] as PaneId[]).filter(p => visiblePanes.has(p));

  const renderPaneContent = (pane: PaneId) => {
    switch (pane) {
      case 'chat': return <ChatPanel />;
      case 'code': return <EditorPanel />;
      case 'preview': return <Preview />;
    }
  };

  return (
    <div className="flex-1 min-h-0 flex flex-row overflow-hidden relative">
      <div ref={panesContainerRef} className="flex-1 min-w-0 flex flex-row overflow-hidden">
        {visiblePaneList.map((pane, i) => (
          <div key={pane} className="contents">
            {i > 0 && (
              <Resizer
                direction="horizontal"
                onDrag={(delta) => handlePaneResize(visiblePaneList[i - 1], pane, delta)}
              />
            )}
            <div
              style={{ flexBasis: `${paneSizes[pane]}%`, flexGrow: 0, flexShrink: 0, minWidth: 0 }}
              className="overflow-hidden flex flex-col min-h-0 h-full"
            >
              <div className="flex-1 min-h-0 h-full overflow-hidden">
                {renderPaneContent(pane)}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="absolute right-3 top-1/2 -translate-y-1/2 z-20 flex flex-col gap-1 p-1.5 rounded-xl bg-surface/90 backdrop-blur-lg border border-border/60 shadow-xl opacity-60 hover:opacity-100 transition-opacity duration-200">
        {(Object.entries(PANE_CONFIG) as [PaneId, typeof PANE_CONFIG[PaneId]][]).map(([id, { icon: Icon, label }]) => {
          const isActive = visiblePanes.has(id);
          return (
            <button
              key={id}
              onClick={() => togglePane(id)}
              title={`${isActive ? 'Hide' : 'Show'} ${label}`}
              className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150 ${
                isActive
                  ? 'text-primary bg-primary/15 shadow-sm'
                  : 'text-muted-foreground/50 hover:text-foreground hover:bg-muted/60'
              }`}
            >
              <Icon size={18} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
