import type { Preview } from '@storybook/react-vite';
import '../src/App.css';

const preview: Preview = {
  parameters: {
    backgrounds: {
      default: 'dark',
      values: [
        { name: 'dark', value: '#181825' },
        { name: 'light', value: '#f5f5f7' },
      ],
    },
    layout: 'centered',
  },
  decorators: [
    (Story) => {
      document.documentElement.dataset.theme = 'dark';
      return Story();
    },
  ],
};

export default preview;
