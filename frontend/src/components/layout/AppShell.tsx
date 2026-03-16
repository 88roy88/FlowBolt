import { useState } from 'react';
import { Sidebar } from './Sidebar';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Terminal } from '../terminal/Terminal';
import { ServerLog } from '../terminal/ServerLog';
import { Preview } from '../preview/Preview';

type BottomTab = 'terminal' | 'server' | 'preview';

export function AppShell() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [bottomTab, setBottomTab] = useState<BottomTab>('server');

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: sidebarOpen ? '250px 1fr' : '0px 1fr',
      gridTemplateRows: '1fr',
      height: '100%',
      width: '100%',
      overflow: 'hidden',
      transition: 'grid-template-columns 0.2s ease',
    }}>
      {/* Sidebar */}
      <div style={{
        overflow: 'hidden',
        borderRight: sidebarOpen ? '1px solid var(--border)' : 'none',
        background: 'var(--surface)',
      }}>
        {sidebarOpen && <Sidebar />}
      </div>

      {/* Main area */}
      <div style={{
        display: 'grid',
        gridTemplateRows: '1fr 300px',
        overflow: 'hidden',
      }}>
        {/* Top: Chat + Editor */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          overflow: 'hidden',
        }}>
          <div style={{ borderRight: '1px solid var(--border)', overflow: 'hidden' }}>
            <ChatPanel />
          </div>
          <div style={{ overflow: 'hidden' }}>
            <EditorPanel />
          </div>
        </div>

        {/* Bottom: Terminal/Preview tabs */}
        <div style={{
          borderTop: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          {/* Tab bar */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0',
            borderBottom: '1px solid var(--border)',
            background: 'var(--surface)',
            flexShrink: 0,
          }}>
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
              onClick={() => setBottomTab('server')}
              style={{
                padding: '6px 16px',
                fontSize: '13px',
                color: bottomTab === 'server' ? 'var(--accent)' : 'var(--text-dim)',
                borderBottom: bottomTab === 'server' ? '2px solid var(--accent)' : '2px solid transparent',
              }}
            >
              Server
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

          {/* Tab content */}
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
