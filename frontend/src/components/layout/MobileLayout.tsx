import { useState } from 'react';
import { MessageSquare, Eye, Menu } from 'lucide-react';
import { ChatPanel } from '../chat/ChatPanel';
import { Preview } from '../preview/Preview';
import { Sidebar } from './Sidebar';
import { GlobalProgress } from './GlobalProgress';
import { FlowBrand } from '../ui/flow-logo';
import { PromptInput } from '../chat/PromptInput';
import { useChatStore } from '../../stores/chat';

type MobileTab = 'chat' | 'preview';

export function MobileLayout() {
  const [activeTab, setActiveTab] = useState<MobileTab>('chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const messages = useChatStore((s) => s.messages);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const historyLoaded = useChatStore((s) => s.historyLoaded);

  const isEmptyState = historyLoaded && messages.length === 0 && !isStreaming;

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      {/* Top bar */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface shrink-0">
        <button onClick={() => setSidebarOpen(true)} className="p-1.5 rounded-md hover:bg-muted/50">
          <Menu size={20} className="text-primary/70" />
        </button>
        <FlowBrand size="sm" />
        <div className="w-9" /> {/* Spacer to center the logo */}
      </div>

      <GlobalProgress />

      {/* Content */}
      {isEmptyState ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-5 px-6 relative overflow-hidden">
          {/* Background glow */}
          <div className="absolute top-1/3 start-1/2 -translate-x-1/2 w-[400px] h-[400px] rounded-full bg-[radial-gradient(circle,color-mix(in_srgb,var(--primary)_8%,transparent),transparent_70%)] pointer-events-none" />
          <div className="relative z-10 flex flex-col items-center gap-5 w-full">
            <div className="relative">
              <div className="absolute inset-0 blur-2xl bg-[color-mix(in_srgb,var(--primary)_20%,transparent)] scale-[2] pointer-events-none" />
              <div className="relative drop-shadow-[0_0_16px_color-mix(in_srgb,var(--primary)_30%,transparent)]">
                <FlowBrand size="lg" />
              </div>
            </div>
            <p className="text-sm text-muted-foreground text-center leading-relaxed">
              Describe what you want to build and the AI will generate it for you.
            </p>
            <div className="w-full rounded-2xl border border-primary/20 shadow-[0_2px_20px_color-mix(in_srgb,var(--primary)_6%,transparent)] [&>div]:border-t-0 [&>div]:rounded-2xl">
              <PromptInput />
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-hidden">
          {activeTab === 'chat' ? <ChatPanel /> : <Preview />}
        </div>
      )}

      {/* Bottom tab bar */}
      {!isEmptyState && (
        <div className="flex items-center border-t border-border bg-surface shrink-0">
          {([
            { id: 'chat' as MobileTab, icon: MessageSquare, label: 'Chat' },
            { id: 'preview' as MobileTab, icon: Eye, label: 'Preview' },
          ]).map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex-1 flex flex-col items-center gap-0.5 py-2.5 transition-colors ${
                activeTab === id
                  ? 'text-primary'
                  : 'text-muted-foreground'
              }`}
            >
              <Icon size={20} />
              <span className="text-[11px] font-medium">{label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Sidebar drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <div className="relative w-[280px] h-full bg-surface border-e border-border shadow-2xl animate-[slideIn_0.2s_ease-out]">
            <Sidebar onCloseSidebar={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
