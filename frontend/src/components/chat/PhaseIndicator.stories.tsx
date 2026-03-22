import type { Meta, StoryObj } from '@storybook/react-vite';
import { PhaseIndicator } from './PhaseIndicator';

const meta: Meta<typeof PhaseIndicator> = {
  title: 'Chat/PhaseIndicator',
  component: PhaseIndicator,
};
export default meta;

export const Classifying: StoryObj = { args: { phase: 'classifying' } };
export const Designing: StoryObj = { args: { phase: 'designing' } };
export const Planning: StoryObj = { args: { phase: 'planning' } };
export const AwaitingApproval: StoryObj = { args: { phase: 'awaiting_approval' } };
export const Executing: StoryObj = { args: { phase: 'executing' } };
export const Fixing: StoryObj = { args: { phase: 'fixing' } };
export const Exploring: StoryObj = { args: { phase: 'exploring' } };
export const Complete: StoryObj = { args: { phase: 'complete' } };

export const AllPhases: StoryObj = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxWidth: 400 }}>
      <PhaseIndicator phase="classifying" />
      <PhaseIndicator phase="designing" />
      <PhaseIndicator phase="planning" />
      <PhaseIndicator phase="awaiting_approval" />
      <PhaseIndicator phase="executing" />
      <PhaseIndicator phase="fixing" />
      <PhaseIndicator phase="exploring" />
      <PhaseIndicator phase="complete" />
    </div>
  ),
};
