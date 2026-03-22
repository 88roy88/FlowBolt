/** Shared mock data used across API mocks and assertions. */

export const PROJECT_ID = 'e2e-test-project-001';
/** @deprecated Alias kept so WS mock scripts still resolve. Equals PROJECT_ID. */
export const SESSION_ID = PROJECT_ID;

export const MOCK_PROJECT = {
  id: PROJECT_ID,
  name: 'E2E Test Project',
  created_at: new Date().toISOString(),
  model: 'mock/test-model',
};

export const MOCK_FILE_TREE = [
  { name: 'src', type: 'directory' as const, children: [
    { name: 'App.tsx', type: 'file' as const, path: 'src/App.tsx' },
    { name: 'main.tsx', type: 'file' as const, path: 'src/main.tsx' },
    { name: 'index.css', type: 'file' as const, path: 'src/index.css' },
  ]},
  { name: 'package.json', type: 'file' as const, path: 'package.json' },
  { name: 'index.html', type: 'file' as const, path: 'index.html' },
];

export const MOCK_APP_TSX = `import React from 'react';
export default function App() {
  return <h1>Hello from E2E</h1>;
}`;

export const MOCK_MODELS = [
  { id: 'mock/test-model', name: 'Test Model' },
];

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
