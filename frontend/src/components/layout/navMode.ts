import { createContext, useContext } from 'react';

export type NavMode = 'sidebar' | 'topbar';

export function loadNavMode(): NavMode {
  try {
    if (localStorage.getItem('nav-mode') === 'topbar') return 'topbar';
  } catch {}
  return 'sidebar';
}

export const NavModeContext = createContext<NavMode>('sidebar');

/** True when project-level actions (panel tabs, share, publish) live in the topbar instead of the panels. */
export const useActionsInTopbar = () => useContext(NavModeContext) === 'topbar';
