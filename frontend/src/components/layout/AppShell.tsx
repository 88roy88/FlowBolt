import { useState, useRef, useCallback } from 'react';
import { PanelLeftOpen } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Terminal } from '../terminal/Terminal';
import { Preview } from '../preview/Preview';

const SIDEBAR_MIN = 180;
const SIDEBAR_MAX = 420;
const BOTTOM_MIN = 120;
const BOTTOM_MAX = 600;
const MAIN_SPLIT_MIN = 0.2;
const MAIN_SPLIT_MAX = 0.8;

type BottomTab = 'terminal' | 'preview';

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [bottomHeight, setBottomHeight] = useState(300);
  const [mainSplit, setMainSplit] = useState(0.5);
  const [bottomTab, setBottomTab] = useState<BottomTab>('terminal');
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

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'row',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}
    >
      {/* When closed: vertical \"Projects\" tab on the left. When open: full projects sidebar with internal close button. */}
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
          style={{
            width: '48px',
            flexShrink: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '4px',
            background: 'var(--surface)',
            border: 'none',
            borderRight: '1px solid var(--border)',
            color: 'var(--accent)',
            cursor: 'pointer',
            fontSize: '10px',
            fontWeight: 600,
          }}
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
          <div
            style={{
              flex: mainSplit,
              minWidth: 0,
              overflow: 'hidden',
            }}
          >
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
            background: 'var(--surface)',
            boxShadow: 'var(--shadow-subtle-top)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 0,
              borderBottom: '1px solid var(--border)',
              background: 'var(--surface)',
              flexShrink: 0,
            }}
          >
            <button
              onClick={() => setBottomTab('terminal')}
              style={{
                padding: 'var(--space-md) var(--space-lg)',
                fontSize: '13px',
                color: bottomTab === 'terminal' ? 'var(--accent)' : 'var(--text-dim)',
                borderBottom: bottomTab === 'terminal' ? '2px solid var(--accent)' : '2px solid transparent',
                background: bottomTab === 'terminal' ? 'rgba(var(--accent-rgb), 0.14)' : 'transparent',
              }}
            >
              Terminal
            </button>

            <button
              onClick={() => setBottomTab('preview')}
              style={{
                padding: 'var(--space-md) var(--space-lg)',
                fontSize: '13px',
                color: bottomTab === 'preview' ? 'var(--accent)' : 'var(--text-dim)',
                borderBottom: bottomTab === 'preview' ? '2px solid var(--accent)' : '2px solid transparent',
                background: bottomTab === 'preview' ? 'rgba(var(--accent-rgb), 0.14)' : 'transparent',
              }}
            >
              Preview
            </button>
          </div>

          <div style={{ flex: 1, overflow: 'hidden' }}>
            {bottomTab === 'terminal' ? <Terminal /> : <Preview />}
          </div>
        </div>
      </div>
    </div>
  );
}