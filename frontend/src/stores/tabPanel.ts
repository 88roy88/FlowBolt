import { create } from 'zustand';

export type PanelTab = 'preview' | 'code';

interface TabPanelState {
  tab: PanelTab;
  setTab: (tab: PanelTab) => void;
}

export const useTabPanelStore = create<TabPanelState>((set) => ({
  tab: 'preview',
  setTab: (tab) => set({ tab }),
}));
