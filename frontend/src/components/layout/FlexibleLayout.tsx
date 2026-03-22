import { useState, useRef, useCallback, useEffect } from 'react';
import { MessageSquare, Code2, Eye, Globe, Loader2 } from 'lucide-react';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Preview } from '../preview/Preview';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { publishToS3 } from '../../services/api';
import { PublishModal } from '../ui/PublishModal';
import { ExternalLink } from 'lucide-react';

type PaneId = 'chat' | 'code' | 'preview';

const PANE_CONFIG: Record<PaneId, { icon: typeof MessageSquare; label: string }> = {
  chat: { icon: MessageSquare, label: 'Chat' },
  code: { icon: Code2, label: 'Code' },
  preview: { icon: Eye, label: 'Preview' },
};

const MIN_PANE_PCT = 20;
const STORAGE_KEY = 'flexible-layout';

function loadLayout(): { visible: PaneId[]; sizes: Record<PaneId, number> } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const { visible, sizes } = JSON.parse(raw);
      if (Array.isArray(visible) && visible.length > 0) {
        return { visible, sizes: { chat: 50, code: 50, preview: 50, ...sizes } };
      }
    }
  } catch {}
  return { visible: ['chat', 'preview'], sizes: { chat: 50, code: 50, preview: 50 } };
}

function saveLayout(visible: Set<PaneId>, sizes: Record<PaneId, number>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ visible: [...visible], sizes }));
  } catch {}
}

export function FlexibleLayout() {
  const [initial] = useState(loadLayout);
  const [visiblePanes, setVisiblePanes] = useState<Set<PaneId>>(new Set(initial.visible));
  const [paneSizes, setPaneSizes] = useState<Record<PaneId, number>>(initial.sizes);
  const panesContainerRef = useRef<HTMLDivElement>(null);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const sessionId = useSessionStore((s) => s.sessionId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishModalState, setPublishModalState] = useState<{ open: boolean; url?: string; error?: string }>({ open: false });
  
  const isPublished = !!currentProject?.published_url;

  const handlePublish = useCallback(async () => {
    if (!sessionId || isPublishing) return;
    setIsPublishing(true);
    try {
      const result = await publishToS3(sessionId);
      const current = useSessionStore.getState().currentProject;
      if (current) {
        useSessionStore.getState().setProjectPublishedUrl(current.id, result.url);
      }
      setPublishModalState({ open: true, url: result.url });
    } catch (err) {
      setPublishModalState({ open: true, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setIsPublishing(false);
    }
  }, [sessionId, isPublishing]);

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
      saveLayout(next, newSizes);
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
      const updated = { ...prev, [leftPane]: newLeft, [rightPane]: newRight };
      saveLayout(visiblePanes, updated);
      return updated;
    });
  }, [visiblePanes]);

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

        <div className="w-9 h-px bg-border/40 my-1 mx-auto" />

        {isPublished && sessionId && (
          <a
            title="View Published App"
            href={`/api/export/${sessionId}/published`}
            target="_blank"
            rel="noopener noreferrer"
            className="w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150 text-secondary-foreground bg-secondary/70 hover:bg-secondary/90 shadow-sm"
          >
            <ExternalLink size={16} />
          </a>
        )}

        <button
          title={isPublished ? "Republish" : "Publish to S3"}
          disabled={!sessionId || isPublishing}
          onClick={handlePublish}
          className={`w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150 ${
            sessionId && !isPublishing
              ? 'text-primary bg-primary/10 hover:bg-primary hover:text-primary-foreground shadow-sm cursor-pointer'
              : 'text-muted-foreground/30 bg-muted/20 cursor-not-allowed'
          }`}
        >
          {isPublishing ? <Loader2 size={16} className="animate-spin" /> : <Globe size={16} />}
        </button>
      </div>
      
      <PublishModal 
        open={publishModalState.open} 
        onOpenChange={(open) => setPublishModalState(s => ({ ...s, open }))}
        url={publishModalState.url}
        errorMessage={publishModalState.error}
      />
    </div>
  );
}
