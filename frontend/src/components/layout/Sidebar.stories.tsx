import type { Meta, StoryObj } from '@storybook/react-vite';
import { useState, useRef } from 'react';
import { Sidebar } from './Sidebar';
import { FlowLogo } from '../ui/flow-logo';

const meta: Meta = {
  title: 'Layout/Sidebar',
  parameters: {
    layout: 'fullscreen',
  },
};
export default meta;

const PROJECT_COLORS = [
  'bg-[#89b4fa]/20 text-[#89b4fa]',
  'bg-[#a6e3a1]/20 text-[#a6e3a1]',
  'bg-[#f9e2af]/20 text-[#f9e2af]',
  'bg-[#cba6f7]/20 text-[#cba6f7]',
  'bg-[#f38ba8]/20 text-[#f38ba8]',
  'bg-[#94e2d5]/20 text-[#94e2d5]',
  'bg-[#fab387]/20 text-[#fab387]',
  'bg-[#74c7ec]/20 text-[#74c7ec]',
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

const mockProjects = [
  { id: '1', name: 'Dashboard App' },
  { id: '2', name: 'Landing Page' },
  { id: '3', name: 'Todo List' },
  { id: '4', name: 'Chat Bot' },
  { id: '5', name: 'E-commerce' },
];

function IconRailDemo({ projects, activeId, onSelect, onExpand }: {
  projects: typeof mockProjects;
  activeId: string;
  onSelect: (id: string) => void;
  onExpand: () => void;
}) {
  return (
    <div className="flex flex-col items-center h-full py-2 gap-1">
      <button onClick={onExpand} title="Expand sidebar" className="mb-1 shrink-0">
        <FlowLogo size={18} className="text-[#2bbcc4]" />
      </button>
      <div className="w-6 h-px bg-border shrink-0" />
      <div className="flex-1 flex flex-col items-center gap-1.5 py-1 overflow-hidden">
        {projects.map((p) => (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            className={`w-8 h-8 rounded-md text-[10px] font-bold flex items-center justify-center transition-all duration-150 shrink-0 ${
              p.id === activeId
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
}

export const SidebarDrawer: StoryObj = {
  render: () => {
    const [pinned, setPinned] = useState(false);
    const [hover, setHover] = useState(false);
    const [closing, setClosing] = useState(false);
    const hoverLock = useRef(false);
    const visible = pinned || hover || closing;
    const [activeId, setActiveId] = useState('1');

    const close = () => {
      setPinned(false);
      setHover(false);
      setClosing(true);
      hoverLock.current = true;
      setTimeout(() => { setClosing(false); hoverLock.current = false; }, 250);
    };

    return (
      <div className="flex h-[600px] bg-background text-foreground">
        <div
          className="relative shrink-0"
          onMouseEnter={() => { if (!hoverLock.current) setHover(true); }}
          onMouseLeave={() => { if (!pinned) close(); }}
        >
          <div className="w-12 h-full bg-surface border-r border-border flex flex-col">
            <IconRailDemo
              projects={mockProjects}
              activeId={activeId}
              onSelect={setActiveId}
              onExpand={() => setPinned(true)}
            />
          </div>

          {visible && (
            <div
              className={`absolute top-0 left-0 z-30 h-full bg-surface border-r border-border shadow-[var(--shadow-lg)] ${
                closing ? 'animate-[slideOut_0.2s_ease-in_forwards]' : 'animate-[slideIn_0.25s_ease-out]'
              }`}
              style={{ width: 280 }}
            >
              <div className="p-4 text-sm text-muted-foreground">
                <div className="flex items-center justify-between mb-4">
                  <span className="font-semibold text-foreground">Projects</span>
                  <div className="flex gap-1">
                    {!pinned ? (
                      <button onClick={() => setPinned(true)} className="p-1 rounded hover:bg-muted/50 text-muted-foreground" title="Pin open">
                        📌
                      </button>
                    ) : (
                      <button onClick={close} className="p-1 rounded hover:bg-muted/50 text-muted-foreground" title="Unpin">
                        📌
                      </button>
                    )}
                  </div>
                </div>
                {mockProjects.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => setActiveId(p.id)}
                    className={`flex items-center gap-2.5 px-2 py-1.5 rounded-md cursor-pointer mb-0.5 transition-colors ${
                      p.id === activeId ? 'bg-muted/60' : 'hover:bg-muted/30'
                    }`}
                  >
                    <div className={`w-7 h-7 rounded-md flex items-center justify-center text-[11px] font-bold shrink-0 ${getColor(p.name)}`}>
                      {getInitials(p.name)}
                    </div>
                    <span className="text-[13px]">{p.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          <p>{pinned ? 'Sidebar is pinned — click 📌 to unpin' : 'Hover the icon rail to expand'}</p>
        </div>
      </div>
    );
  },
};

export const IconRailOnly: StoryObj = {
  render: () => {
    const [activeId, setActiveId] = useState('1');
    return (
      <div className="flex h-[500px] bg-background text-foreground">
        <div className="w-12 bg-surface border-r border-border">
          <IconRailDemo
            projects={mockProjects}
            activeId={activeId}
            onSelect={setActiveId}
            onExpand={() => {}}
          />
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Active: {mockProjects.find((p) => p.id === activeId)?.name}
        </div>
      </div>
    );
  },
};

export const IconRailManyProjects: StoryObj = {
  render: () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      id: String(i),
      name: `Project ${i + 1}`,
    }));
    const [activeId, setActiveId] = useState('0');
    return (
      <div className="flex h-[400px] bg-background text-foreground">
        <div className="w-12 bg-surface border-r border-border">
          <IconRailDemo
            projects={many}
            activeId={activeId}
            onSelect={setActiveId}
            onExpand={() => {}}
          />
        </div>
        <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
          Shows overflow clipping with many projects
        </div>
      </div>
    );
  },
};
