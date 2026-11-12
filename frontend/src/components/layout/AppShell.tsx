import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Sidebar } from './Sidebar';
import { GlobalProgress } from './GlobalProgress';
import { SettingsModal } from './SettingsModal';
import { ClassicLayout } from './ClassicLayout';
import { FlexibleLayout } from './FlexibleLayout';
import { MobileLayout } from './MobileLayout';
import { BottomDrawer } from './BottomDrawer';
import { PreviewVersionBanner } from '../preview/PreviewVersionBanner';
import { PublishModal } from '../publish/PublishModal';
import { AdminPanel } from '../admin/AdminPanel';
import { FlowBrand, FlowLogo } from '../ui/flow-logo';
import { PromptInput } from '../chat/PromptInput';
import { Settings, Shield } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { useWorkspaceLock } from '../../stores/workspaceLock';
import { useIsMobile } from '../../hooks/useIsMobile';
import { startProjectFromPrompt } from '../../utils/newProject';
import { isPlainClick, projectHref } from '../../utils/links';
import { openProject } from '../../utils/openProject';
import { ProjectAvatar } from './ProjectAvatar';
import { TopBar } from './TopBar';
import { getProjectHasMessages, setProjectHasMessages } from '../../utils/projectHasMessagesCache';

const SIDEBAR_WIDTH = 280;
const RAIL_WIDTH = 56;
type LayoutMode = 'classic' | 'flexible';
export type NavMode = 'sidebar' | 'topbar';

function loadNavMode(): NavMode {
  try {
    if (localStorage.getItem('nav-mode') === 'topbar') return 'topbar';
  } catch {}
  return 'sidebar';
}

function loadLayoutMode(): LayoutMode {
  try {
    const v = localStorage.getItem('layout-mode');
    if (v === 'classic' || v === 'flexible') return v;
  } catch {}
  return 'classic';
}

function loadSidebarExpanded(): boolean {
  try {
    return localStorage.getItem('sidebar-expanded') === 'true';
  } catch {
    return false;
  }
}

export function AppShell() {
  const { t } = useTranslation();
  const isMobile = useIsMobile();

  const [sidebarExpanded, setSidebarExpanded] = useState(loadSidebarExpanded);

  const toggleSidebar = (expanded: boolean) => {
    setSidebarExpanded(expanded);
    try { localStorage.setItem('sidebar-expanded', expanded ? 'true' : 'false'); } catch {}
  };

  // Layout + settings
  const [layoutMode, setLayoutMode] = useState<LayoutMode>(loadLayoutMode);
  const [showSettings, setShowSettings] = useState(false);
  const [showAdminPanel, setShowAdminPanel] = useState(false);

  const switchLayout = (mode: LayoutMode) => {
    setLayoutMode(mode);
    try { localStorage.setItem('layout-mode', mode); } catch {}
  };

  const [navMode, setNavMode] = useState<NavMode>(loadNavMode);
  const switchNav = (mode: NavMode) => {
    setNavMode(mode);
    try { localStorage.setItem('nav-mode', mode); } catch {}
  };

  // Shared state
  const { lock } = useWorkspaceLock();
  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const historyLoaded = useChatStore((s) => s.historyLoaded);
  const projects = useSessionStore((s) => s.projects);
  const currentProject = useSessionStore((s) => s.currentProject);
  const userStatus = useSessionStore((s) => s.userStatus);
  const isCreating = useSessionStore((s) => s.isCreating);
  const canCreate = userStatus?.is_platform_user || userStatus?.is_admin;

  // Use cache to determine layout before history loads to prevent flicker
  // Read project ID from URL hash immediately (don't wait for currentProject to be set)
  const urlProjectId = window.location.hash.match(/^#\/project\/(.+)$/)?.[1];
  const projectIdForCache = currentProject?.id || urlProjectId;
  const cachedHasMessages = projectIdForCache ? getProjectHasMessages(projectIdForCache) : null;

  const isNewProject = !projectIdForCache || (historyLoaded
    ? (messages.length === 0 && !isStreaming)
    : cachedHasMessages === false);
  const isEmptyState = historyLoaded && messages.length === 0 && !isStreaming;

  // Update cache after history loads
  useEffect(() => {
    if (historyLoaded && currentProject) {
      const hasMessages = messages.length > 0;
      setProjectHasMessages(currentProject.id, hasMessages);
    }
  }, [historyLoaded, messages.length, currentProject?.id]);

  const handleHint = (hint: string) => {
    if (currentProject) useChatStore.getState().sendMessage(hint);
    else void startProjectFromPrompt(hint);
  };


  const IconRail = () => (
    <div className="flex flex-col items-center h-full py-2 gap-1">
      <button onClick={() => toggleSidebar(true)} title={t('sidebar.expandSidebar')} className="mb-1 shrink-0">
        <FlowLogo size={18} className="text-brand" />
      </button>
      <div className="w-8 h-px bg-border shrink-0" />
      <div className="flex-1 flex flex-col items-center gap-1.5 px-1 py-1 overflow-y-auto overflow-x-visible">
        {projects.map((p) => (
          <a
            key={p.id}
            href={projectHref(p.id)}
            onClick={(e) => {
              if (!isPlainClick(e)) return;
              e.preventDefault();
              openProject(p, 'icon_rail');
            }}
            className={`shrink-0 transition-all duration-150 ${
              p.id === currentProject?.id ? 'ring-1 ring-primary/40 rounded-md' : 'opacity-50 hover:opacity-100'
            }`}
            title={p.name}
          >
            <ProjectAvatar name={p.name} size="lg" />
          </a>
        ))}
      </div>
      <div className="w-8 h-px bg-border shrink-0" />
      {userStatus?.is_admin && (
        <button
          onClick={() => setShowAdminPanel(true)}
          title={t('admin.title', 'Platform Users')}
          className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors shrink-0"
        >
          <Shield size={16} className="text-warning/70" />
        </button>
      )}
      <button
        onClick={() => setShowSettings(true)}
        title={t('common.settings')}
        className="w-8 h-8 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors shrink-0"
      >
        <Settings size={16} className="text-primary/70" />
      </button>
    </div>
  );


  if (isMobile) return <MobileLayout />;

  return (
    <div className="flex flex-row h-full w-full overflow-hidden" style={{ boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.03)' }}>
      {navMode === 'sidebar' && (
      <div
        className="relative shrink-0 h-full bg-surface border-e border-border overflow-hidden transition-[width] duration-200 ease-out"
        style={{ width: sidebarExpanded ? SIDEBAR_WIDTH : RAIL_WIDTH }}
      >
        <div
          inert={sidebarExpanded}
          className={`absolute inset-y-0 start-0 transition-opacity duration-150 ${sidebarExpanded ? 'opacity-0' : 'opacity-100'}`}
          style={{ width: RAIL_WIDTH }}
        >
          <IconRail />
        </div>
        <div
          inert={!sidebarExpanded}
          className={`absolute inset-y-0 start-0 transition-opacity duration-150 ${sidebarExpanded ? 'opacity-100' : 'opacity-0'}`}
          style={{ width: SIDEBAR_WIDTH }}
        >
          <Sidebar onCollapse={() => toggleSidebar(false)} onOpenSettings={() => setShowSettings(true)} onOpenAdmin={() => setShowAdminPanel(true)} />
        </div>
      </div>
      )}

      {/* Main content */}
      <div className="flex-1 min-w-0 flex flex-col overflow-hidden">
        {navMode === 'topbar' && (
          <TopBar onOpenSettings={() => setShowSettings(true)} onOpenAdmin={() => setShowAdminPanel(true)} />
        )}
        <GlobalProgress />
        <PreviewVersionBanner />

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
                {t('onboarding.tagline')}
              </p>
              <div className="w-full">
                <PromptInput />
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                {[t('onboarding.hintDashboard'), t('onboarding.hintTodoApp'), t('onboarding.hintLandingPage')].map((hint) => (
                  <button
                    key={hint}
                    onClick={() => handleHint(hint)}
                    disabled={lock !== null || isCreating || (!currentProject && !canCreate)}
                    className="px-3 py-1.5 text-xs bg-primary/5 text-primary/60 border border-primary/20 rounded-full hover:bg-primary/10 hover:border-primary/40 hover:text-primary transition-all duration-150 cursor-pointer"
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
          navMode={navMode}
          onNavChange={switchNav}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showAdminPanel && <AdminPanel onClose={() => setShowAdminPanel(false)} />}

      <PublishModal />
    </div>
  );
}
