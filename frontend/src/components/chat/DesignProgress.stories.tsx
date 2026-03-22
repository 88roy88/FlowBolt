import type { Meta, StoryObj } from '@storybook/react-vite';
import { DesignProgress } from './DesignProgress';

const meta: Meta<typeof DesignProgress> = {
  title: 'Chat/DesignProgress',
  component: DesignProgress,
  decorators: [(Story) => <div style={{ maxWidth: 500 }}><Story /></div>],
};
export default meta;

export const BothInProgress: StoryObj = {
  args: { designProgress: { architecture: null, ux: null } },
};

export const ArchitectureDone: StoryObj = {
  args: { designProgress: { architecture: 'complete', ux: null } },
};

export const BothDone: StoryObj = {
  args: { designProgress: { architecture: 'complete', ux: 'complete' } },
};
