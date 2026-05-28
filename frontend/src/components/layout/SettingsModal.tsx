import { useState, useEffect, forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import { X, LayoutPanelLeft, Columns3, Bell, Languages } from 'lucide-react';
import { Button } from '../ui/button';
import { isNotifyEnabled, setNotifyEnabled, requestPermissionIfNeeded } from '../../utils/notifications';

export type LayoutMode = 'classic' | 'flexible';

type SettingsPopoverProps = {
  layoutMode: LayoutMode;
  onLayoutChange: (mode: LayoutMode) => void;
  onClose: () => void;
};

export const SettingsPopover = forwardRef<HTMLDivElement, SettingsPopoverProps>(
  ({ layoutMode, onLayoutChange, onClose }, ref) => {
    const { t, i18n } = useTranslation();
    const [notifyOn, setNotifyOn] = useState(isNotifyEnabled);
    const currentLanguage = i18n.language;

    useEffect(() => {
      const handler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') onClose();
      };
      document.addEventListener('keydown', handler);
      return () => document.removeEventListener('keydown', handler);
    }, [onClose]);

    const changeLanguage = (lang: string) => {
      i18n.changeLanguage(lang);
      localStorage.setItem('language', lang);
    };

    return (
      <div
        ref={ref}
        className="absolute bottom-full mb-2 start-0 end-0 bg-surface border border-border rounded-xl shadow-2xl z-50 animate-card-in"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <h2 className="text-[13px] font-semibold">{t('settings.title')}</h2>
          <Button variant="ghost" size="icon-sm" onClick={onClose}>
            <X size={14} />
          </Button>
        </div>

        {/* Content */}
        <div className="px-4 py-3 space-y-4">
          {/* Layout mode */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">{t('settings.layout')}</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => onLayoutChange('classic')}
                className={`flex flex-col items-center gap-1.5 p-2.5 rounded-lg border transition-all duration-150 ${
                  layoutMode === 'classic'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <LayoutPanelLeft size={20} />
                <div className="text-center">
                  <div className="text-[12px] font-medium">{t('settings.layoutClassic')}</div>
                  <div className="text-[10px] opacity-70">{t('settings.layoutClassicDesc')}</div>
                </div>
              </button>
              <button
                onClick={() => onLayoutChange('flexible')}
                className={`flex flex-col items-center gap-1.5 p-2.5 rounded-lg border transition-all duration-150 ${
                  layoutMode === 'flexible'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Columns3 size={20} />
                <div className="text-center">
                  <div className="text-[12px] font-medium">{t('settings.layoutFlexible')}</div>
                  <div className="text-[10px] opacity-70">{t('settings.layoutFlexibleDesc')}</div>
                </div>
              </button>
            </div>
          </div>

          {/* Notifications */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">{t('settings.notifications')}</label>
            <button
              onClick={() => {
                const next = !notifyOn;
                setNotifyEnabled(next);
                setNotifyOn(next);
                if (next) requestPermissionIfNeeded();
              }}
              className={`flex items-center gap-2.5 p-2.5 rounded-lg border transition-all duration-150 w-full ${
                notifyOn
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
              }`}
            >
              <Bell size={16} />
              <span className="text-[13px] font-medium">
                {notifyOn ? t('settings.buildAlertsOn') : t('settings.buildAlertsOff')}
              </span>
            </button>
          </div>

          {/* Language */}
          <div className="space-y-2">
            <label className="text-[12px] font-medium text-muted-foreground uppercase tracking-wide">{t('settings.language')}</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => changeLanguage('en')}
                className={`flex items-center gap-2 p-2.5 rounded-lg border transition-all duration-150 ${
                  currentLanguage === 'en'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Languages size={16} />
                <span className="text-[13px] font-medium">{t('settings.english')}</span>
              </button>
              <button
                onClick={() => changeLanguage('he')}
                className={`flex items-center gap-2 p-2.5 rounded-lg border transition-all duration-150 ${
                  currentLanguage === 'he'
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border hover:border-primary/30 hover:bg-muted/30 text-muted-foreground'
                }`}
              >
                <Languages size={16} />
                <span className="text-[13px] font-medium">{t('settings.hebrew')}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
);

SettingsPopover.displayName = 'SettingsPopover';

// Kept for backwards-compat import (AppShell still imports SettingsModal until updated)
export { SettingsPopover as SettingsModal };
