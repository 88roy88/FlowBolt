import type { Meta, StoryObj } from '@storybook/react-vite';
import { FollowUpProgress } from './FollowUpProgress';

const meta: Meta<typeof FollowUpProgress> = {
  title: 'Chat/Cards/FollowUpProgress',
  component: FollowUpProgress,
  decorators: [(Story) => <div style={{ maxWidth: 550 }}><Story /></div>],
};
export default meta;

export const Exploring: StoryObj = {
  args: {
    steps: [
      { id: '1', tool: 'grep', args: { pattern: 'fetchData', path: '/src' }, status: 'completed', resultPreview: 'src/hooks/useData.ts:15\nsrc/App.tsx:42', iteration: 1 },
      { id: '2', tool: 'read_file', args: { path: '/src/hooks/useData.ts' }, status: 'completed', resultPreview: 'export function useData() {\n  const [data, setData] = useState(null);\n  ...', iteration: 1 },
      { id: '3', tool: 'glob', args: { pattern: 'src/components/**/*.tsx' }, status: 'running', iteration: 2 },
    ],
    isLive: true,
  },
};

export const CompletedWithAnswer: StoryObj = {
  args: {
    steps: [
      { id: '1', tool: 'grep', args: { pattern: 'useState', path: '/src' }, status: 'completed', resultPreview: 'Found 12 matches', iteration: 1 },
      { id: '2', tool: 'read_file', args: { path: '/src/App.tsx' }, status: 'completed', iteration: 1 },
    ],
    answer: 'The app uses `useState` in 12 places across the codebase. The main state management is in `App.tsx` which holds the global config, and individual components manage their own local state.',
  },
};

export const WithFileEdits: StoryObj = {
  args: {
    steps: [
      { id: '1', tool: 'read_file', args: { path: '/src/components/Header.tsx' }, status: 'completed', iteration: 1 },
      { id: '2', tool: 'edit_file', args: { path: '/src/components/Header.tsx' }, status: 'completed', iteration: 1 },
      { id: '3', tool: 'write_file', args: { path: '/src/components/Footer.tsx' }, status: 'completed', iteration: 1 },
    ],
    filesChanged: ['/src/components/Header.tsx', '/src/components/Footer.tsx'],
    diffs: [
      {
        path: 'src/components/Header.tsx',
        diff: '@@ -5,3 +5,5 @@\n function Header() {\n   return (\n-    <header>\n+    <header className="bg-blue-500 text-white p-4">\n+      <h1>My App</h1>\n     </header>',
      },
    ],
    answer: 'I updated the Header component with proper styling and added a new Footer component.',
  },
};

export const ManySteps: StoryObj = {
  args: {
    steps: [
      { id: '1', tool: 'glob', args: { pattern: '**/*.tsx' }, status: 'completed', resultPreview: '24 files found', iteration: 1 },
      { id: '2', tool: 'grep', args: { pattern: 'import.*axios' }, status: 'completed', resultPreview: 'No matches', iteration: 1 },
      { id: '3', tool: 'grep', args: { pattern: 'fetch\\(' }, status: 'completed', resultPreview: 'src/api.ts:12\nsrc/api.ts:28', iteration: 2 },
      { id: '4', tool: 'read_file', args: { path: '/src/api.ts' }, status: 'completed', iteration: 2 },
      { id: '5', tool: 'read_file', args: { path: '/src/hooks/useApi.ts' }, status: 'completed', iteration: 3 },
      { id: '6', tool: 'edit_file', args: { path: '/src/api.ts' }, status: 'completed', iteration: 3 },
    ],
    answer: 'Refactored the API layer to use a centralized `request()` helper with proper error handling.',
    filesChanged: ['/src/api.ts'],
  },
};
