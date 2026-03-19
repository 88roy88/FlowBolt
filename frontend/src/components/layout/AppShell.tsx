import { useState, useRef, useCallback } from 'react';
import { PanelLeftOpen } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Preview } from '../preview/Preview';

const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 420;
const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;
const MAIN_SPLIT_MIN = 0.2;
const MAIN_SPLIT_MAX = 0.8;

type BottomTab = 'terminal' | 'server' | 'preview';

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [bottomTab, setBottomTab] = useState<BottomTab>('server');
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [bottomHeight, setBottomHeight] = useState(300);
  const [mainSplit, setMainSplit] = useState(0.5);
  const mainTopRef = useRef<HTMLDivElement>(null);

  const handleSidebarResize = useCallback((delta: number) => {
    setSidebarWidth((w) => Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, w + delta)));
  }, []);

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

  const bottomTabs: { id: BottomTab; label: string }[] = [
    { id: 'server', label: 'Server' },
    { id: 'terminal', label: 'Terminal' },
    { id: 'preview', label: 'Preview' },
  ];

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        boxShadow: 'inset 0 1px 0 0 rgba(255,255,255,0.03)',
      }}
    >
      {sidebarOpen ? (
        <>
          <div
            style={{
              width: sidebarWidth,
              minWidth: sidebarWidth,
              overflow: 'hidden',
              borderRight: '1px solid var(--border)',
              background: 'var(--surface)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Sidebar onCloseSidebar={() => setSidebarOpen(false)} />
          </div>
          <Resizer direction="horizontal" onDrag={handleSidebarResize} />
        </>
      ) : (
        <button
          type="button"
          onClick={() => setSidebarOpen(true)}
          title="Show projects panel"
          className="w-12 shrink-0 flex flex-col items-center justify-center gap-1 bg-surface border-r border-border text-primary cursor-pointer text-[10px] font-semibold hover:bg-muted/30 transition-colors"
        >
          <PanelLeftOpen size={22} />
          <span>Projects</span>
        </button>
      )}

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <div
          ref={mainTopRef}
          style={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'row',
            overflow: 'hidden',
          }}
        >
          <div style={{ flex: mainSplit, minWidth: 0, overflow: 'hidden' }}>
            <ChatPanel />
          </div>
          <Resizer direction="horizontal" onDrag={handleMainSplitResize} />
          <div style={{ flex: 1 - mainSplit, minWidth: 0, overflow: 'hidden' }}>
            <EditorPanel />
          </div>
        </div>

        <Resizer direction="vertical" onDrag={handleBottomResize} />

        <div
          style={{
            height: bottomHeight,
            minHeight: BOTTOM_MIN,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flexShrink: 0,
          }}
        >
          {/* Bottom tab bar */}
          <div className="flex items-center border-b border-border bg-surface shrink-0">
            {bottomTabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setBottomTab(tab.id)}
                className={`px-4 py-1.5 text-[13px] font-medium border-b-2 transition-colors duration-150 ${
                  bottomTab === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ flex: 1, overflow: 'hidden' }}>
            {bottomTab === 'terminal' && <Terminal />}
            {bottomTab === 'server' && <ServerLog />}
            {bottomTab === 'preview' && <Preview />}
          </div>
        </div>
      </div>
    </div>
  );
}
