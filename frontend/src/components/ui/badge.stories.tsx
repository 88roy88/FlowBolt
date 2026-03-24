import type { Meta, StoryObj } from '@storybook/react-vite';
import { Badge } from './badge';

const meta: Meta<typeof Badge> = {
  title: 'UI/Badge',
  component: Badge,
  argTypes: {
    variant: { control: 'select', options: ['default', 'accent', 'muted', 'success', 'destructive'] },
  },
};
export default meta;

type Story = StoryObj<typeof Badge>;

export const Default: Story = { args: { children: 'Badge' } };
export const Accent: Story = { args: { variant: 'accent', children: 'Data source #4' } };
export const Success: Story = { args: { variant: 'success', children: 'Complete' } };
export const Destructive: Story = { args: { variant: 'destructive', children: 'Error' } };

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', gap: 8 }}>
      <Badge>Default</Badge>
      <Badge variant="accent">Accent</Badge>
      <Badge variant="muted">Muted</Badge>
      <Badge variant="success">Success</Badge>
      <Badge variant="destructive">Error</Badge>
    </div>
  ),
};
