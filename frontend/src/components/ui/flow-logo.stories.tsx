import type { Meta, StoryObj } from '@storybook/react-vite';
import { FlowLogo, FlowBrand } from './flow-logo';

const meta: Meta = {
  title: 'UI/FlowBrand',
};
export default meta;

export const LogoIcon: StoryObj = {
  render: () => (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
      <FlowLogo size={16} className="text-[#2bbcc4]" />
      <FlowLogo size={24} className="text-[#2bbcc4]" />
      <FlowLogo size={32} className="text-[#2bbcc4]" />
      <FlowLogo size={48} className="text-[#2bbcc4]" />
    </div>
  ),
};

export const BrandSizes: StoryObj = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <FlowBrand size="sm" />
      <FlowBrand size="md" />
      <FlowBrand size="lg" />
    </div>
  ),
};
