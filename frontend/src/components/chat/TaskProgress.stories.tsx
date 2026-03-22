import type { Meta, StoryObj } from '@storybook/react-vite';
import { TaskProgress } from './TaskProgress';

const meta: Meta<typeof TaskProgress> = {
  title: 'Chat/TaskProgress',
  component: TaskProgress,
  decorators: [(Story) => <div style={{ maxWidth: 500 }}><Story /></div>],
};
export default meta;

export const JustStarted: StoryObj = {
  args: {
    tasks: [
      { id: '1', title: 'Set up project structure', status: 'running' },
      { id: '2', title: 'Create authentication flow', status: 'pending' },
      { id: '3', title: 'Build dashboard components', status: 'pending' },
      { id: '4', title: 'Add settings page', status: 'pending' },
    ],
  },
};

export const Midway: StoryObj = {
  args: {
    tasks: [
      { id: '1', title: 'Set up project structure', status: 'completed' },
      { id: '2', title: 'Create authentication flow', status: 'completed' },
      { id: '3', title: 'Build dashboard components', status: 'running' },
      { id: '4', title: 'Add settings page', status: 'pending' },
    ],
  },
};

export const AllComplete: StoryObj = {
  args: {
    tasks: [
      { id: '1', title: 'Set up project structure', status: 'completed' },
      { id: '2', title: 'Create authentication flow', status: 'completed' },
      { id: '3', title: 'Build dashboard components', status: 'completed' },
      { id: '4', title: 'Add settings page', status: 'completed' },
    ],
  },
};

export const WithFailure: StoryObj = {
  args: {
    tasks: [
      { id: '1', title: 'Set up project structure', status: 'completed' },
      { id: '2', title: 'Create authentication flow', status: 'completed' },
      { id: '3', title: 'Build dashboard components', status: 'failed' },
      { id: '4', title: 'Add settings page', status: 'pending' },
    ],
  },
};

export const ManyTasks: StoryObj = {
  args: {
    tasks: Array.from({ length: 10 }, (_, i) => ({
      id: String(i),
      title: `Task ${i + 1}: ${['Create layout', 'Add routing', 'Build API layer', 'Style components', 'Add forms', 'Write tests', 'Add auth', 'Set up DB', 'Deploy config', 'Final polish'][i]}`,
      status: i < 6 ? 'completed' : i === 6 ? 'running' : 'pending' as 'completed' | 'running' | 'pending',
    })),
  },
};
