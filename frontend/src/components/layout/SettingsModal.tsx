import { useState } from 'react';
import { X, LayoutPanelLeft, Columns3, Moon, Sun, Bell } from 'lucide-react';
import { Button } from '../ui/button';
import { isNotifyEnabled, setNotifyEnabled, requestPermissionIfNeeded } from '../../utils/notifications';

export type LayoutMode = 'classic' | 'flexible';

type SettingsModalProps = {
  layoutMode: LayoutMode;
  onLayoutChange: (mode: LayoutMode) => void;
  onClose: () => void;
};

export function SettingsModal({ layoutMode, onLayoutChange, onClose }: SettingsModalProps) {
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
  const [notifyOn, setNotifyOn] = useState(isNotifyEnabled);

  const setTheme = (theme: 'dark' | 'light') => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface border border-border rounded-xl shadow-2xl w-full max-w-md mx-4 animate-card-in">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-base font-semibold">Settings</h2>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X size={16} />
          </Button>
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-5">
          {/* Layout mode */}
          <div className="space-y-2.5">
            <label className="text-[13px] font-medium text-foreground">Layout</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => onLayoutChange('classic')}
                className={`flex flex-col items-center gap-2 p-3 rounded-lg border transition-all duration-150 ${
                  layoutMode === 'classic'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <LayoutPanelLeft size={24} />
                <div className="text-center">
                  <div className="text-[13px] font-medium">Classic</div>
                  <div className="text-[11px] opacity-70">Chat + tabbed panels</div>
                </div>
              </button>
              <button
                onClick={() => onLayoutChange('flexible')}
                className={`flex flex-col items-center gap-2 p-3 rounded-lg border transition-all duration-150 ${
                  layoutMode === 'flexible'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Columns3 size={24} />
                <div className="text-center">
                  <div className="text-[13px] font-medium">Flexible</div>
                  <div className="text-[11px] opacity-70">Independent panels</div>
                </div>
              </button>
            </div>
          </div>

          {/* Theme */}
          <div className="space-y-2.5">
            <label className="text-[13px] font-medium text-foreground">Theme</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setTheme('dark')}
                className={`flex items-center gap-2.5 p-3 rounded-lg border transition-all duration-150 ${
                  currentTheme === 'dark'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Moon size={18} />
                <span className="text-[13px] font-medium">Dark</span>
              </button>
              <button
                onClick={() => setTheme('light')}
                className={`flex items-center gap-2.5 p-3 rounded-lg border transition-all duration-150 ${
                  currentTheme === 'light'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Sun size={18} />
                <span className="text-[13px] font-medium">Light</span>
              </button>
            </div>
          </div>

          {/* Notifications */}
          <div className="space-y-2.5">
            <label className="text-[13px] font-medium text-foreground">Notifications</label>
            <button
              onClick={() => {
                const next = !notifyOn;
                setNotifyEnabled(next);
                setNotifyOn(next);
                if (next) requestPermissionIfNeeded();
              }}
              className={`flex items-center gap-2.5 p-3 rounded-lg border transition-all duration-150 w-full ${
                notifyOn
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
              }`}
            >
              <Bell size={18} />
              <span className="text-[13px] font-medium">
                {notifyOn ? 'Build alerts on' : 'Build alerts off'}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
