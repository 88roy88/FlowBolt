/** Shared mock data used across API mocks and assertions. */

import type { FileEntry } from '../../src/types';

export const PROJECT_ID = 'e2e-test-project-001';

export const MOCK_PROJECT = {
  id: PROJECT_ID,
  name: 'E2E Test Project',
  created_at: new Date().toISOString(),
  model: 'mock/test-model',
  published_url: '',
  published_at: null as string | null,
};

/** A second mock project used to simulate a taken slug in publish tests. */
export const MOCK_PROJECT_WITH_SLUG = {
  id: 'e2e-test-project-002',
  name: 'Published Project',
  created_at: new Date().toISOString(),
  model: 'mock/test-model',
  published_url: 'taken-slug',
  published_at: new Date().toISOString(),
};

/** Matches backend `FileEntry` shape (`is_directory`, leading `/` on paths). */
export const MOCK_FILE_TREE: FileEntry[] = [
  {
    name: 'src',
    path: '/src',
    is_directory: true,
    children: [
      { name: 'App.tsx', path: '/src/App.tsx', is_directory: false },
      { name: 'types.ts', path: '/src/types.ts', is_directory: false },
      { name: 'main.tsx', path: '/src/main.tsx', is_directory: false },
      { name: 'index.css', path: '/src/index.css', is_directory: false },
    ],
  },
  { name: 'package.json', path: '/package.json', is_directory: false },
  { name: 'index.html', path: '/index.html', is_directory: false },
];

export const MOCK_APP_TSX = `import { Todo } from './types';

export default function App() {
  const _sample: Todo = { id: 'e2e' };
  return <h1>Hello from E2E</h1>;
}
`;

export const MOCK_TYPES_TS = `export interface Todo {
  id: string;
}
// E2E_TYPES_MARKER
`;

export const MOCK_MAIN_TSX = `import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(<App />);
`;

/** Minimal replay so ClassicLayout leaves "new project" mode and shows Preview/Code. */
export const CHAT_SEED_EVENTS = [
  { type: 'user_message', content: 'E2E bootstrap' },
  { type: 'text', content: 'Initial assistant response' },
  { type: 'action_complete' },
];

/** Path keys without leading slash — matches API ?path= after normalization. */
export const MOCK_FILE_CONTENTS: Record<string, string> = {
  'src/App.tsx': MOCK_APP_TSX,
  'src/types.ts': MOCK_TYPES_TS,
  'src/main.tsx': MOCK_MAIN_TSX,
  'src/index.css': '/* e2e */',
  'package.json': '{"name":"e2e"}',
  'index.html': '<!DOCTYPE html><html><body><div id="root"></div></body></html>',
};

export const MOCK_MODELS = [{ id: 'mock/test-model', name: 'Test Model' }];

/** A scripted build sequence — the events the chat WebSocket sends during a build. */
export const BUILD_EVENT_SEQUENCE = [
  { type: 'user_message', content: 'Build a todo app' },
  { type: 'phase', phase: 'designing' },
  { type: 'design_progress', stream: 'architecture', content: 'complete' },
  { type: 'design_progress', stream: 'ux', content: 'complete' },
  { type: 'phase', phase: 'planning' },
  {
    type: 'plan_overview',
    overview: {
      summary: 'A simple todo app with add, remove, and toggle functionality.',
      tasks: [
        { id: 'task-1', title: 'Create types', description: 'TypeScript interfaces', files: ['src/types.ts'], depends_on: [] },
        { id: 'task-2', title: 'Create App', description: 'Main app component', files: ['src/App.tsx'], depends_on: ['task-1'] },
      ],
    },
  },
  // After plan approval:
  { type: 'phase', phase: 'executing' },
  { type: 'task_start', task_id: 'task-1', title: 'Create types' },
  { type: 'task_complete', task_id: 'task-1', title: 'Create types' },
  { type: 'task_start', task_id: 'task-2', title: 'Create App' },
  { type: 'task_complete', task_id: 'task-2', title: 'Create App' },
  { type: 'phase', phase: 'idle' },
  { type: 'action_complete', summary: 'Built a todo app with 2 tasks.' },
];
