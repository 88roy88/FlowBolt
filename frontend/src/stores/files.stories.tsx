import type { Meta, StoryObj } from '@storybook/react-vite';

import { useFilesStore } from './files';

const meta = {
  component: useFilesStore,
} satisfies Meta<typeof useFilesStore>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Default: Story = {};