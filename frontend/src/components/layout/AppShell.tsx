import { useState, useRef, useCallback, useEffect } from 'react';
import { ChevronUp, MessageSquare, Code2, Eye } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Resizer } from './Resizer';
import { GlobalProgress } from './GlobalProgress';
import { SettingsModal } from './SettingsModal';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Preview } from '../preview/Preview';
import { FlowBrand, FlowLogo } from '../ui/flow-logo';
import { PromptInput } from '../chat/PromptInput';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';

const SIDEBAR_WIDTH = 280;
const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;
const MAIN_SPLIT_MIN = 0.2;
const MAIN_SPLIT_MAX = 0.8;

type BottomTab = 'terminal' | 'server';
type RightTab = 'preview' | 'code';
type PaneId = 'chat' | 'code' | 'preview';
type LayoutMode = 'classic' | 'flexible';

const PANE_CONFIG: Record<PaneId, { icon: typeof MessageSquare; label: string }> = {
  chat: { icon: MessageSquare, label: 'Chat' },
  code: { icon: Code2, label: 'Code' },
  preview: { icon: Eye, label: 'Preview' },
};

function loadLayoutMode(): LayoutMode {
  try {
    const v = localStorage.getItem('layout-mode');
    if (v === 'classic' || v === 'flexible') return v;
  } catch {}
  return 'classic';
}

export function AppShell() {
  // Sidebar
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const [sidebarHover, setSidebarHover] = useState(false);
  const [sidebarClosing, setSidebarClosing] = useState(false);
  const hoverLockRef = useRef(false);

  const closeSidebar = () => {
    setSidebarPinned(false);
    setSidebarHover(false);
    setSidebarClosing(true);
    hoverLockRef.current = true;
    setTimeout(() => { setSidebarClosing(false); hoverLockRef.current = false; }, 250);
  };

  // Bottom drawer
  const [bottomOpen, setBottomOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>('server');
  const [bottomHeight, setBottomHeight] = useState(250);

  // Layout mode
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(loadLayoutMode);

  const [showSettings, setShowSettings] = useState(false);

  const switchLayout = (mode: LayoutMode) => {
    setLayoutMode(mode);
    try { localStorage.setItem('layout-mode', mode); } catch {}
  };

  // Classic layout state
  const [rightTab, setRightTab] = useState<RightTab>('preview');
  const [mainSplit, setMainSplit] = useState(0.4);
  const mainTopRef = useRef<HTMLDivElement>(null);

  // Flexible layout state
  const [visiblePanes, setVisiblePanes] = useState<Set<PaneId>>(new Set(['chat', 'preview']));
  const [paneSizes, setPaneSizes] = useState<Record<PaneId, number>>({ chat: 50, code: 50, preview: 50 });
  const panesContainerRef = useRef<HTMLDivElement>(null);

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

  const MIN_PANE_PCT = 20;

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

  // Shared state
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const projects = useSessionStore((s) => s.projects);
  const currentProject = useSessionStore((s) => s.currentProject);

  const isEmptyState = messages.length === 0 && !isStreaming;

  useEffect(() => {
    if (agentPhase === 'executing' || agentPhase === 'complete') {
      if (layoutMode === 'classic') setRightTab('preview');
      else setVisiblePanes(prev => new Set([...prev, 'preview']));
    }
  }, [agentPhase, layoutMode]);

  const handleBottomResize = useCallback((delta: number) => {
    setBottomHeight((h) => Math.min(BOTTOM_MAX, Math.max(BOTTOM_MIN, h - delta)));
  }, []);

  const handleMainSplitResize = useCallback((delta: number) => {
    const el = mainTopRef.current;
    if (!el) return;
    const width = el.getBoundingClientRect().width;
    if (width <= 0) return;
    setMainSplit((s) => Math.min(MAIN_SPLIT_MAX, Math.max(MAIN_SPLIT_MIN, s + delta / width)));
  }, []);

  // Shared helpers
  const PROJECT_COLORS = [
    'bg-[#89b4fa]/20 text-[#89b4fa]', 'bg-[#a6e3a1]/20 text-[#a6e3a1]',
    'bg-[#f9e2af]/20 text-[#f9e2af]', 'bg-[#cba6f7]/20 text-[#cba6f7]',
    'bg-[#f38ba8]/20 text-[#f38ba8]', 'bg-[#94e2d5]/20 text-[#94e2d5]',
    'bg-[#fab387]/20 text-[#fab387]', 'bg-[#74c7ec]/20 text-[#74c7ec]',
  ];

  function getColor(name: string) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
    return PROJECT_COLORS[Math.abs(h) % PROJECT_COLORS.length];
  }

  function getInitials(name: string) {
    const w = name.trim().split(/\s+/);
    return w.length >= 2 ? (w[0][0] + w[1][0]).toUpperCase() : name.slice(0, 2).toUpperCase();
  }

  const handleRailSelect = (p: typeof projects[number]) => {
    useSessionStore.getState().setCurrentProject(p);
    window.location.hash = `#/project/${p.session_id}`;
    useFilesStore.getState().reset();
    useFilesStore.getState().loadFileTree();
    useChatStore.getState().loadHistory(p.session_id);
  };

  const IconRail = () => (
    <div className="flex flex-col items-center h-full py-2 gap-1">
      <button onClick={() => setSidebarPinned(true)} title="Expand sidebar" className="mb-1 shrink-0">
        <FlowLogo size={18} className="text-[#2bbcc4]" />
      </button>
      <div className="w-8 h-px bg-border shrink-0" />
      <div className="flex-1 flex flex-col items-center gap-1.5 py-1 overflow-hidden">
        {projects.map((p) => (
          <button
            key={p.id}
            onClick={() => handleRailSelect(p)}
            className={`w-8 h-8 rounded-md text-xs font-bold flex items-center justify-center transition-all duration-150 shrink-0 ${
              p.id === currentProject?.id
                ? `${getColor(p.name)} ring-1 ring-primary/40`
                : `${getColor(p.name)} opacity-50 hover:opacity-100`
            }`}
            title={p.name}
          >
            {getInitials(p.name)}
          </button>
        ))}
      </div>
    </div>
  );

  const visiblePaneList = (['chat', 'code', 'preview'] as PaneId[]).filter(p => visiblePanes.has(p));

  const renderPaneContent = (pane: PaneId) => {
    switch (pane) {
      case 'chat': return <ChatPanel />;
      case 'code': return <EditorPanel />;
      case 'preview': return <Preview />;
    }
  };

  // Bottom drawer (shared between both layouts)
  const BottomDrawer = () => (
    <div className="border-t border-border bg-surface shrink-0">
      <button
        onClick={() => setBottomOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground hover:bg-muted/30 transition-colors"
      >
        <ChevronUp size={14} className={`transition-transform duration-200 ${!bottomOpen ? '' : 'rotate-180'}`} />
        <span className="font-medium">{bottomTab === 'server' ? 'Server Log' : 'Terminal'}</span>
        {!bottomOpen && (
          <div className="flex gap-2 ml-auto">
            {(['server', 'terminal'] as BottomTab[]).map((tab) => (
              <button
                key={tab}
                onClick={(e) => { e.stopPropagation(); setBottomTab(tab); setBottomOpen(true); }}
                className={`px-2 py-0.5 rounded text-[11px] capitalize ${
                  bottomTab === tab ? 'text-foreground' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        )}
      </button>
      {bottomOpen && (
        <>
          <div className="flex items-center border-t border-border shrink-0">
            {(['server', 'terminal'] as BottomTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setBottomTab(tab)}
                className={`px-4 py-1.5 text-[13px] font-medium border-b-2 transition-colors duration-150 capitalize ${
                  bottomTab === tab
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab === 'server' ? 'Server' : 'Terminal'}
              </button>
            ))}
          </div>
          <div style={{ height: bottomHeight }}>
            <Resizer direction="vertical" onDrag={handleBottomResize} />
            <div style={{ height: bottomHeight - 1 }} className="overflow-hidden">
              {bottomTab === 'terminal' ? <Terminal /> : <ServerLog />}
            </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="flex flex-row h-full w-full overflow-hidden" style={{ boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.03)' }}>
      {/* Sidebar */}
      {sidebarPinned ? (
        <div
          className="shrink-0 bg-surface border-r border-border flex flex-col animate-[slideIn_0.25s_ease-out]"
          style={{ width: SIDEBAR_WIDTH }}
        >
          <Sidebar onCloseSidebar={closeSidebar} isPinned={true} onPin={() => setSidebarPinned(true)} onOpenSettings={() => setShowSettings(true)} />
        </div>
      ) : (
        <div
          className="relative shrink-0"
          onMouseEnter={() => { if (!hoverLockRef.current) setSidebarHover(true); }}
          onMouseLeave={() => closeSidebar()}
        >
          <div className="w-14 h-full bg-surface border-r border-border flex flex-col">
            <IconRail />
          </div>
          {(sidebarHover || sidebarClosing) && (
            <div
              className={`absolute top-0 left-0 z-30 h-full bg-surface border-r border-border shadow-[var(--shadow-lg)] ${
                sidebarClosing ? 'animate-[slideOut_0.2s_ease-in_forwards]' : 'animate-[slideIn_0.25s_ease-out]'
              }`}
              style={{ width: SIDEBAR_WIDTH }}
            >
              <Sidebar onCloseSidebar={closeSidebar} isPinned={false} onPin={() => { setSidebarPinned(true); setSidebarHover(false); }} onOpenSettings={() => setShowSettings(true)} />
            </div>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <GlobalProgress />

        {isEmptyState ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8">
            <FlowBrand size="lg" />
            <p className="text-base text-muted-foreground max-w-md text-center leading-relaxed">
              Describe what you want to build and the AI will design, plan, and code it for you.
            </p>
            <div className="w-full max-w-2xl">
              <PromptInput />
            </div>
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {['A dashboard with charts', 'A todo app with drag & drop', 'A landing page with animations'].map((hint) => (
                <button
                  key={hint}
                  onClick={() => useChatStore.getState().sendMessage(hint)}
                  className="px-3 py-1.5 text-xs text-foreground/80 bg-muted/40 border border-border/80 rounded-full shadow-[var(--shadow-sm)] hover:border-primary/50 hover:text-primary hover:bg-accent-bg transition-all duration-150 cursor-pointer"
                >
                  {hint}
                </button>
              ))}
            </div>
          </div>
        ) : layoutMode === 'classic' ? (
          /* ========== CLASSIC LAYOUT ========== */
          <>
            <div ref={mainTopRef} className="flex-1 min-h-0 flex flex-row overflow-hidden relative">
              {/* Chat (always visible) */}
              <div style={{ flex: mainSplit, minWidth: 0 }} className="overflow-hidden">
                <ChatPanel />
              </div>

              <Resizer direction="horizontal" onDrag={handleMainSplitResize} />

              {/* Right: Preview / Code tabs */}
              <div style={{ flex: 1 - mainSplit, minWidth: 0 }} className="overflow-hidden flex flex-col">
                <div className="flex items-center border-b border-border bg-surface shrink-0">
                  {(['preview', 'code'] as RightTab[]).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setRightTab(tab)}
                      className={`px-4 py-2 text-[13px] font-medium border-b-2 transition-colors duration-150 capitalize ${
                        rightTab === tab
                          ? 'border-primary text-primary'
                          : 'border-transparent text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>
                <div className="flex-1 overflow-hidden">
                  {rightTab === 'preview' ? <Preview /> : <EditorPanel />}
                </div>
              </div>

            </div>
            <BottomDrawer />
          </>
        ) : (
          /* ========== FLEXIBLE LAYOUT ========== */
          <>
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
                      className="overflow-hidden flex flex-col"
                    >
                      <div className="flex-1 overflow-hidden">
                        {renderPaneContent(pane)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Floating pane toggles */}
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
            <BottomDrawer />
          </>
        )}
      </div>

      {showSettings && (
        <SettingsModal
          layoutMode={layoutMode}
          onLayoutChange={switchLayout}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
