import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronUp, Shield } from 'lucide-react';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Console } from '../terminal/Console';
import { DataSourcesPanel } from '../dataSources/DataSourcesPanel';
import { FlowLogo } from '../ui/flow-logo';
import { Resizer } from './Resizer';
import { useSessionStore } from '../../stores/session';
import { WRITE_ROLES } from '../../types';

type BottomTab = 'dataSources' | 'terminal' | 'server' | 'console';

const TAB_LABEL_KEYS: Record<BottomTab, string> = {
  dataSources: 'dataSources.title',
  server: 'terminal.server',
  terminal: 'terminal.terminal',
  console: 'terminal.console',
};

const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;

export function BottomDrawer() {
  const { t } = useTranslation();
  const currentProject = useSessionStore((s) => s.currentProject);
  const canUseTerminal = useSessionStore((s) => !!s.userStatus?.can_use_terminal);
  const terminalAdminOnly = useSessionStore((s) => !!s.userStatus?.terminal_admin_only);
  const canWrite = !currentProject?.role || WRITE_ROLES.has(currentProject.role);
  const showTerminal = canWrite && canUseTerminal;
  const bottomTabs: BottomTab[] = showTerminal
    ? ['dataSources', 'server', 'terminal', 'console']
    : ['dataSources', 'server', 'console'];

  const [bottomOpen, setBottomOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>('dataSources');
  const [bottomHeight, setBottomHeight] = useState(250);

  const handleBottomResize = useCallback((delta: number) => {
    setBottomHeight((h) => Math.min(BOTTOM_MAX, Math.max(BOTTOM_MIN, h - delta)));
  }, []);

  const tabLabel = (tab: BottomTab) => t(TAB_LABEL_KEYS[tab]);

  const panel = () => {
    if (bottomTab === 'dataSources') return <DataSourcesPanel />;
    if (bottomTab === 'console') return <Console />;
    return bottomTab === 'terminal' && showTerminal ? <Terminal /> : <ServerLog />;
  };

  const tabIcon = (tab: BottomTab, size: number) => tab === 'dataSources' && <FlowLogo size={size} />;

  const adminBadge = (tab: BottomTab, size: number, className?: string) =>
    tab === 'terminal' && terminalAdminOnly && (
      <span title={t('terminal.adminOnly')} className="inline-flex">
        <Shield size={size} className={className} />
      </span>
    );

  return (
    <div className="relative border-t border-border bg-surface shrink-0">
      {/* Straddles the drawer's top edge, so the line it highlights is that border. */}
      {bottomOpen && (
        <div className="absolute inset-x-0 -top-1">
          <Resizer direction="vertical" onDrag={handleBottomResize} />
        </div>
      )}
      {/* One bar whether open or closed. Clicking anywhere on it that isn't a tab opens or closes the drawer. */}
      <div
        data-testid="bottom-drawer-bar"
        onClick={() => setBottomOpen((v) => !v)}
        className="flex items-center cursor-pointer hover:bg-muted/30 transition-colors"
      >
        {/* No handler of its own: its click reaches the bar. */}
        <button
          aria-expanded={bottomOpen}
          aria-label={t(bottomOpen ? 'terminal.collapsePanel' : 'terminal.expandPanel')}
          title={t(bottomOpen ? 'terminal.collapsePanel' : 'terminal.expandPanel')}
          className="self-stretch inline-flex items-center ps-3 text-muted-foreground hover:text-foreground"
        >
          <ChevronUp size={15} className={`transition-transform duration-200 ${bottomOpen ? 'rotate-180' : ''}`} />
        </button>
        {bottomTabs.map((tab) => (
          <button
            key={tab}
            onClick={(e) => { e.stopPropagation(); setBottomTab(tab); setBottomOpen(true); }}
            // The underline stops short of the tab's edges, which keeps it clear of the arrow.
            className={`relative inline-flex items-center gap-1.5 px-4 pt-1.5 pb-2 text-[13px] font-medium transition-colors duration-150 after:absolute after:inset-x-2.5 after:bottom-0 after:h-0.5 ${
              bottomOpen && bottomTab === tab
                ? 'text-primary after:bg-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tabIcon(tab, 13)}
            {tabLabel(tab)}
            {adminBadge(tab, 13)}
          </button>
        ))}
      </div>
      {bottomOpen && (
        <div className="overflow-hidden border-t border-border" style={{ height: bottomHeight }}>
          {panel()}
        </div>
      )}
    </div>
  );
}
