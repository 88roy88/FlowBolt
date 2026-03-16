import { useState, useRef, useCallback } from 'react';
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
      <div
        style={{
          width: sidebarOpen ? sidebarWidth : 0,
          minWidth: sidebarOpen ? sidebarWidth : 0,
          overflow: 'hidden',
          borderRight: sidebarOpen ? '1px solid var(--border)' : 'none',
          background: 'var(--surface)',
          transition: sidebarOpen ? 'none' : 'width 0.2s ease, min-width 0.2s ease',
        }}
      >
        {sidebarOpen && <Sidebar />}
      </div>

      {sidebarOpen && <Resizer direction="horizontal" onDrag={handleSidebarResize} />}

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
              borderRight: '1px solid var(--border)',
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
            borderTop: '1px solid var(--border)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0',
              borderBottom: '1px solid var(--border)',
              background: 'var(--surface)',
              flexShrink: 0,
            }}
          >
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              style={{
                padding: '6px 10px',
                fontSize: '12px',
                color: 'var(--text-dim)',
                borderRight: '1px solid var(--border)',
              }}
              title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              {sidebarOpen ? '\u25C0' : '\u25B6'}
            </button>

            <button
              onClick={() => setBottomTab('terminal')}
              style={{
                padding: '6px 16px',
                fontSize: '13px',
                color: bottomTab === 'terminal' ? 'var(--accent)' : 'var(--text-dim)',
                borderBottom: bottomTab === 'terminal' ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              Terminal
            </button>

            <button
              onClick={() => setBottomTab('preview')}
              style={{
                padding: '6px 16px',
                fontSize: '13px',
                color: bottomTab === 'preview' ? 'var(--accent)' : 'var(--text-dim)',
                borderBottom: bottomTab === 'preview' ? '2px solid var(--accent)' : '2px solid transparent',
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