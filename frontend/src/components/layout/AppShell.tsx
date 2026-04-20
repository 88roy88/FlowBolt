import { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronUp } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Resizer } from './Resizer';
import { GlobalProgress } from './GlobalProgress';
import { SettingsModal } from './SettingsModal';
import { ClassicLayout } from './ClassicLayout';
import { FlexibleLayout } from './FlexibleLayout';
import { MobileLayout } from './MobileLayout';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Console } from '../terminal/Console';
import { PublishModal } from '../publish/PublishModal';
import { FlowBrand, FlowLogo } from '../ui/flow-logo';
import { PromptInput } from '../chat/PromptInput';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { useFilesStore } from '../../stores/files';
import { useIsMobile } from '../../hooks/useIsMobile';

const SIDEBAR_WIDTH = 280;
const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;

type BottomTab = 'terminal' | 'server' | 'console';
type LayoutMode = 'classic' | 'flexible';

function loadLayoutMode(): LayoutMode {
  try {
    const v = localStorage.getItem('layout-mode');
    if (v === 'classic' || v === 'flexible') return v;
  } catch {}
  return 'classic';
}

function getProjectHasMessages(projectId: string): boolean | null {
  try {
    const v = localStorage.getItem(`project-has-messages:${projectId}`);
    if (v === 'true') return true;
    if (v === 'false') return false;
    return null; // No cache
  } catch {
    return null;
  }
}

function setProjectHasMessages(projectId: string, hasMessages: boolean) {
  try {
    localStorage.setItem(`project-has-messages:${projectId}`, hasMessages ? 'true' : 'false');
  } catch {}
}

export function AppShell() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();

  // All hooks must be called before any conditional returns
  // Sidebar
  const [sidebarPinned, setSidebarPinned] = useState(false);
  const [sidebarHover, setSidebarHover] = useState(false);
  const [sidebarClosing, setSidebarClosing] = useState(false);
  const [sidebarBusy, setSidebarBusy] = useState(false);
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

  // Layout + settings
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(loadLayoutMode);
  const [showSettings, setShowSettings] = useState(false);

  const switchLayout = (mode: LayoutMode) => {
    setLayoutMode(mode);
    try { localStorage.setItem('layout-mode', mode); } catch {}
  };

  // Shared state
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const historyLoaded = useChatStore((s) => s.historyLoaded);
  const projects = useSessionStore((s) => s.projects);
  const currentProject = useSessionStore((s) => s.currentProject);

  // Use cache to determine layout before history loads to prevent flicker
  // Read project ID from URL hash immediately (don't wait for currentProject to be set)
  const urlProjectId = window.location.hash.match(/^#\/project\/(.+)$/)?.[1];
  const projectIdForCache = currentProject?.id || urlProjectId;
  const cachedHasMessages = projectIdForCache ? getProjectHasMessages(projectIdForCache) : null;

  const isNewProject = historyLoaded
    ? (messages.length === 0 && !isStreaming)
    : (cachedHasMessages !== true); // Show empty state unless cache explicitly says has messages
  const isEmptyState = historyLoaded && messages.length === 0 && !isStreaming;

  // Update cache after history loads
  useEffect(() => {
    if (historyLoaded && currentProject) {
      const hasMessages = messages.length > 0;
      setProjectHasMessages(currentProject.id, hasMessages);
    }
  }, [historyLoaded, messages.length, currentProject?.id]);

  const handleBottomResize = useCallback((delta: number) => {
    setBottomHeight((h) => Math.min(BOTTOM_MAX, Math.max(BOTTOM_MIN, h - delta)));
  }, []);

  // Project colors + initials for icon rail
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
    window.location.hash = `#/project/${p.id}`;
    useFilesStore.getState().reset();
    useFilesStore.getState().loadFileTree();
    useChatStore.getState().loadHistory(p.id);
  };

  const IconRail = () => (
    <div className="flex flex-col items-center h-full py-2 gap-1">
      <button onClick={() => setSidebarPinned(true)} title={t('sidebar.expandSidebar')} className="mb-1 shrink-0">
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

  const BottomDrawer = () => (
    <div className="border-t border-border bg-surface shrink-0">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setBottomOpen((v) => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setBottomOpen((v) => !v); }}
        className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground hover:bg-muted/30 transition-colors cursor-pointer"
      >
        <ChevronUp size={14} className={`transition-transform duration-200 ${!bottomOpen ? '' : 'rotate-180'}`} />
        <span className="font-medium">{bottomTab === 'server' ? t('terminal.serverLog') : bottomTab === 'console' ? t('terminal.console') : t('terminal.terminal')}</span>
        {!bottomOpen && (
          <div className="flex gap-2 ms-auto">
            {(['server', 'terminal', 'console'] as BottomTab[]).map((tab) => (
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
      </div>
      {bottomOpen && (
        <>
          <div className="flex items-center border-t border-border shrink-0">
            {(['server', 'terminal', 'console'] as BottomTab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setBottomTab(tab)}
                className={`px-4 py-1.5 text-[13px] font-medium border-b-2 transition-colors duration-150 capitalize ${
                  bottomTab === tab
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab === 'server' ? t('terminal.server') : tab === 'console' ? t('terminal.console') : t('terminal.terminal')}
              </button>
            ))}
          </div>
          <div style={{ height: bottomHeight }}>
            <Resizer direction="vertical" onDrag={handleBottomResize} />
            <div style={{ height: bottomHeight - 1 }} className="overflow-hidden">
              {bottomTab === 'terminal' ? <Terminal /> : bottomTab === 'console' ? <Console /> : <ServerLog />}
            </div>
          </div>
        </>
      )}
    </div>
  );

  if (isMobile) return <MobileLayout />;

  return (
    <div className="flex flex-row h-full w-full overflow-hidden" style={{ boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.03)' }}>
      {/* Sidebar */}
      {sidebarPinned ? (
        <div
          className="shrink-0 bg-surface border-e border-border flex flex-col animate-[slideIn_0.25s_ease-out]"
          style={{ width: SIDEBAR_WIDTH }}
        >
          <Sidebar onCloseSidebar={closeSidebar} isPinned={true} onPin={() => setSidebarPinned(true)} onOpenSettings={() => setShowSettings(true)} onBusyChange={setSidebarBusy} />
        </div>
      ) : (
        <div
          className="relative shrink-0"
          onMouseEnter={() => { if (!hoverLockRef.current) setSidebarHover(true); }}
          onMouseLeave={() => { if (!sidebarBusy) closeSidebar(); }}
        >
          <div className="w-14 h-full bg-surface border-e border-border flex flex-col">
            <IconRail />
          </div>
          {(sidebarHover || sidebarClosing) && (
            <div
              className={`absolute top-0 start-0 z-30 h-full bg-surface border-e border-border shadow-[var(--shadow-lg)] ${
                sidebarClosing ? 'animate-[slideOut_0.2s_ease-in_forwards]' : 'animate-[slideIn_0.25s_ease-out]'
              }`}
              style={{ width: SIDEBAR_WIDTH }}
            >
              <Sidebar onCloseSidebar={closeSidebar} isPinned={false} onPin={() => { setSidebarPinned(true); setSidebarHover(false); }} onOpenSettings={() => setShowSettings(true)} onBusyChange={setSidebarBusy} />
            </div>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <GlobalProgress />

        {isNewProject ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8 relative overflow-hidden">
            {/* Animated glow orb */}
            <div className="absolute top-[25%] start-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--primary)_8%,transparent),transparent_70%)] pointer-events-none animate-[drift_14s_ease-in-out_infinite]" />

            <style>{`
              @keyframes drift { 0%, 100% { transform: translateX(-50%) translate(0, 0); } 33% { transform: translateX(-50%) translate(30px, -20px); } 66% { transform: translateX(-50%) translate(-20px, 15px); } }
            `}</style>

            <div className="relative z-10 flex flex-col items-center gap-6 w-full max-w-2xl">
              {/* Logo with glow */}
              <div className="relative">
                <div className="absolute inset-0 blur-3xl bg-[color-mix(in_srgb,var(--primary)_25%,transparent)] scale-[2] pointer-events-none" />
                <div className="relative drop-shadow-[0_0_20px_color-mix(in_srgb,var(--primary)_30%,transparent)]">
                  <FlowBrand size="lg" />
                </div>
              </div>
              <p className="text-base text-muted-foreground max-w-md text-center leading-relaxed">
                Describe what you want to build and the AI will design, plan,
                and code it for you.
              </p>
              <div className="w-full rounded-2xl bg-surface/80 border border-border/50 shadow-[0_2px_20px_color-mix(in_srgb,var(--primary)_4%,transparent)] [&>div]:border-t-0 [&>div]:rounded-2xl">
                <PromptInput />
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                {['A dashboard with charts', 'A todo app with drag & drop', 'A landing page with animations'].map((hint) => (
                  <button
                    key={hint}
                    onClick={() => useChatStore.getState().sendMessage(hint)}
                    className="px-3 py-1.5 text-xs text-muted-foreground/70 border border-border/50 rounded-full hover:border-primary/40 hover:text-primary transition-all duration-150 cursor-pointer"
                  >
                    {hint}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {layoutMode === 'classic' ? <ClassicLayout /> : <FlexibleLayout />}
            {!isNewProject && !isEmptyState && <BottomDrawer />}
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

      <PublishModal />
    </div>
  );
}
