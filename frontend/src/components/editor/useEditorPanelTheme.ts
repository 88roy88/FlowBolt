import { useEffect, useState } from 'react';

export function useEditorPanelTheme() {
  const [editorTheme, setEditorTheme] = useState<'vs-dark' | 'light'>('vs-dark');

  useEffect(() => {
    const applyTheme = () => {
      const mode = document.documentElement.dataset.theme === 'light' ? 'light' : 'vs-dark';
      setEditorTheme(mode);
    };
    applyTheme();
    const observer = new MutationObserver(() => applyTheme());
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  return editorTheme;
}
