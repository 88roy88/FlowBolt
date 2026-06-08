import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronUp } from 'lucide-react';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Console } from '../terminal/Console';
import { Resizer } from './Resizer';
import { useSessionStore } from '../../stores/session';
import { WRITE_ROLES } from '../../types';

type BottomTab = 'terminal' | 'server' | 'console';

const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;

export function BottomDrawer() {
  const { t } = useTranslation();
  const currentProject = useSessionStore((s) => s.currentProject);
  const canWrite = !currentProject?.role || WRITE_ROLES.has(currentProject.role);
  const bottomTabs: BottomTab[] = canWrite ? ['server', 'terminal', 'console'] : ['server', 'console'];

  const [bottomOpen, setBottomOpen] = useState(false);
  const [bottomTab, setBottomTab] = useState<BottomTab>('server');
  const [bottomHeight, setBottomHeight] = useState(250);

  const handleBottomResize = useCallback((delta: number) => {
    setBottomHeight((h) => Math.min(BOTTOM_MAX, Math.max(BOTTOM_MIN, h - delta)));
  }, []);

  const tabLabel = (tab: BottomTab) =>
    tab === 'server' ? t('terminal.server') : tab === 'console' ? t('terminal.console') : t('terminal.terminal');

  return (
    <div className="border-t border-border bg-surface shrink-0">
      <div
        role="button"
        tabIndex={0}
        onClick={() => setBottomOpen((v) => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setBottomOpen((v) => !v); }}
        className="w-full flex items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground hover:bg-muted/30 transition-colors cursor-pointer"
      >
        <ChevronUp size={14} className={`transition-transform duration-200 ${!bottomOpen ? '' : 'rotate-180'}`} />
        <span className="font-medium">{tabLabel(bottomTab)}</span>
        {!bottomOpen && (
          <div className="flex gap-2 ms-auto">
            {bottomTabs.map((tab) => (
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
            {bottomTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setBottomTab(tab)}
                className={`px-4 py-1.5 text-[13px] font-medium border-b-2 transition-colors duration-150 capitalize ${
                  bottomTab === tab
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tabLabel(tab)}
              </button>
            ))}
          </div>
          <div style={{ height: bottomHeight }}>
            <Resizer direction="vertical" onDrag={handleBottomResize} />
            <div style={{ height: bottomHeight - 1 }} className="overflow-hidden">
              {bottomTab === 'terminal' && canWrite ? <Terminal /> : bottomTab === 'console' ? <Console /> : <ServerLog />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
