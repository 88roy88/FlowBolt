import { useEffect, useState } from 'react';
import { SunMedium, MoonStar } from 'lucide-react';

type Theme = 'light' | 'dark';

function getInitialTheme(): Theme {
  if (typeof document === 'undefined') return 'dark';
  const attr = document.documentElement.dataset.theme;
  if (attr === 'light' || attr === 'dark') return attr;
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => getInitialTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem('theme', theme);
  }, [theme]);

  const isLight = theme === 'light';

  return (
    <button
      type="button"
      onClick={() => setTheme(isLight ? 'dark' : 'light')}
      title={isLight ? 'Switch to dark mode' : 'Switch to light mode'}
      className="absolute top-3 end-3 z-20 flex items-center justify-center w-8 h-8 rounded-full border border-border bg-surface/80 text-muted-foreground hover:text-foreground hover:bg-muted/60 backdrop-blur-sm transition-all cursor-pointer shadow-sm"
    >
      {isLight ? <MoonStar size={16} /> : <SunMedium size={16} />}
    </button>
  );
}
