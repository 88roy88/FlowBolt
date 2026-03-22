import type { Meta, StoryObj } from '@storybook/react-vite';
import { Button } from './button';
import { Check, Pencil, X, Wrench, Plus } from 'lucide-react';

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
  argTypes: {
    variant: { control: 'select', options: ['default', 'destructive', 'success', 'warning', 'outline', 'ghost', 'link'] },
    size: { control: 'select', options: ['default', 'sm', 'lg', 'icon', 'icon-sm'] },
  },
};
export default meta;

type Story = StoryObj<typeof Button>;

export const Default: Story = { args: { children: 'Button' } };
export const Destructive: Story = { args: { variant: 'destructive', children: 'Delete' } };
export const Success: Story = { args: { variant: 'success', children: <><Check size={14} /> Accept</> } };
export const Warning: Story = { args: { variant: 'warning', children: <><Pencil size={14} /> Modify</> } };
export const Outline: Story = { args: { variant: 'outline', children: <><X size={14} /> Cancel</> } };
export const Ghost: Story = { args: { variant: 'ghost', children: 'Ghost' } };
export const IconButton: Story = { args: { variant: 'ghost', size: 'icon', children: <Plus size={16} /> } };
export const Disabled: Story = { args: { children: 'Disabled', disabled: true } };

export const AllVariants: Story = {
  render: () => (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      <Button>Default</Button>
      <Button variant="destructive">Destructive</Button>
      <Button variant="success"><Check size={14} /> Success</Button>
      <Button variant="warning"><Wrench size={14} /> Warning</Button>
      <Button variant="outline">Outline</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="link">Link</Button>
    </div>
  ),
};
