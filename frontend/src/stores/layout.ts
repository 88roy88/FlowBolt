import { create } from 'zustand';

export type RightTab = 'preview' | 'code';

interface LayoutState {
  rightTab: RightTab;
  setRightTab: (tab: RightTab) => void;
}

export const useLayoutStore = create<LayoutState>((set) => ({
  rightTab: 'preview',
  setRightTab: (rightTab) => set({ rightTab }),
}));
