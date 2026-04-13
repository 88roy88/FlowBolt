/**
 * Scripted LLM responses for the full e2e flow.
 *
 * The mock LLM server pops items in FIFO order.
 * Streaming responses use the XML flowArtifact format parsed by ActionParser.
 * Non-streaming responses are plain JSON strings parsed by each agent.
 *
 * Call order:
 *   [0]  PlanAgent: architecture design        (complete_chat, non-streaming, parallel)
 *   [1]  PlanAgent: UX design                  (complete_chat, non-streaming, parallel)
 *   [2]  PlanAgent: first user plan overview   (complete_chat, non-streaming)
 *   [3]  PlanAgent: modified overview          (rebuild_with_feedback after "change something")
 *   [4]  ExecuteAgent: work plan               (complete_chat, non-streaming)
 *   [5]  ExecuteAgent: task-1 codegen FAULTY   (stream_chat, streaming — has TS type error)
 *   [6]  ExecuteAgent: task-2 codegen CSS      (stream_chat, streaming — clean)
 *   [7]  ExecuteAgent: auto-fix attempt        (stream_chat, streaming — fixes the TS error)
 *   [8]  ExecuteAgent: project summary         (complete_chat, non-streaming)
 *   [9]  FixErrorAgent: user-introduced bug    (stream_chat, streaming)
 *   [10] FixErrorAgent: runtime crash button   (stream_chat, streaming)
 *   [11] FollowUpAgent: write dark mode BUGGY  (complete_chat_with_tools → tool_call)
 *   [12] FollowUpAgent: final answer           (complete_chat_with_tools → content only)
 *   [13] FixErrorAgent: followup bug fix       (stream_chat, streaming)
 */

export interface QueuedResponse {
  content?: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
}

// ---------------------------------------------------------------------------
// Shared design JSON — valid for BOTH ArchitectureDesign and UXDesign.
// ---------------------------------------------------------------------------
const DESIGN_JSON = JSON.stringify({
  components: [
    { name: 'App', file: 'src/App.tsx', purpose: 'Main todo list with add/toggle/delete' },
  ],
  data_flow: 'Unidirectional — useState in App, re-renders on change',
  file_structure: ['src/App.tsx', 'src/index.css'],
  state_management: 'React useState hooks',
  key_dependencies: 'React 18, TypeScript',
  notes: '',
  layout: 'Centered card, input at top, list below',
  color_scheme: 'White card on gray bg, indigo (#4f46e5) accent',
  components_ui: [
    { name: 'InputRow', layout: 'Flex row', interactions: 'Enter key or Add button' },
    { name: 'TodoList', layout: 'Vertical ul', interactions: 'Click to toggle, X to delete' },
  ],
  animations: 'None',
  accessibility: 'Keyboard navigation, semantic HTML',
});

// ---------------------------------------------------------------------------
// Plan overview — shown to user for approval (first version)
// ---------------------------------------------------------------------------
const PLAN_OVERVIEW_JSON = JSON.stringify({
  summary: 'A clean todo app where you can add tasks, mark them done, and delete them.',
  features: [
    { title: 'Add todos', description: 'Type in the input and press Enter or click Add' },
    { title: 'Toggle completion', description: 'Click any task to mark it done or undone' },
    { title: 'Delete todos', description: 'Click the ✕ button to permanently remove a task' },
  ],
  decisions: [
    {
      id: 'dec-1',
      title: 'State management',
      chosen: 'React useState (local)',
      alternatives: ['Redux', 'Zustand'],
    },
    {
      id: 'dec-2',
      title: 'Styling',
      chosen: 'Plain CSS',
      alternatives: ['TailwindCSS', 'CSS Modules'],
    },
  ],
});

// Modified overview after "change something" feedback (adds filtering feature)
const PLAN_OVERVIEW_MODIFIED_JSON = JSON.stringify({
  summary: 'A clean todo app with add, complete, delete and filter functionality — updated based on your feedback.',
  features: [
    { title: 'Add todos', description: 'Type in the input and press Enter or click Add' },
    { title: 'Toggle completion', description: 'Click any task to mark it done or undone' },
    { title: 'Delete todos', description: 'Click the ✕ button to permanently remove a task' },
    { title: 'Filter todos', description: 'Show All, Active, or Completed tasks' },
  ],
  decisions: [
    {
      id: 'dec-1',
      title: 'State management',
      chosen: 'React useState (local)',
      alternatives: ['Redux', 'Zustand'],
    },
    {
      id: 'dec-2',
      title: 'Styling',
      chosen: 'Plain CSS',
      alternatives: ['TailwindCSS', 'CSS Modules'],
    },
  ],
});

// ---------------------------------------------------------------------------
// Work plan — ExecuteAgent builds tasks from this
// ---------------------------------------------------------------------------
const WORK_PLAN_JSON = JSON.stringify({
  summary: 'Build a simple todo app with React and TypeScript',
  tasks: [
    {
      id: 'task-1',
      title: 'Create App component',
      description: 'Main component with todo state, input handling, and list rendering',
      files: ['src/App.tsx'],
      depends_on: [],
    },
    {
      id: 'task-2',
      title: 'Add styles',
      description: 'CSS for app layout, input row, and todo items',
      files: ['src/index.css'],
      depends_on: ['task-1'],
    },
  ],
});

// ---------------------------------------------------------------------------
// App.tsx variants
// ---------------------------------------------------------------------------

/** Base clean App.tsx content (reused across multiple responses). */
const APP_TSX_CLEAN = `import { useState } from 'react'
import './index.css'

interface Todo {
  id: number
  text: string
  done: boolean
}

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState<string>('')

  const add = (): void => {
    if (!input.trim()) return
    setTodos(prev => [...prev, { id: Date.now(), text: input.trim(), done: false }])
    setInput('')
  }

  const toggle = (id: number): void =>
    setTodos(prev => prev.map(t => (t.id === id ? { ...t, done: !t.done } : t)))

  const remove = (id: number): void =>
    setTodos(prev => prev.filter(t => t.id !== id))

  return (
    <div className="app">
      <h1>Todo App</h1>
      <div className="input-row">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="Add todo..."
        />
        <button onClick={add}>Add</button>
      </div>
      <ul>
        {todos.map(t => (
          <li key={t.id} className={t.done ? 'done' : ''}>
            <span onClick={() => toggle(t.id)}>{t.text}</span>
            <button onClick={() => remove(t.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}`;

/**
 * FAULTY App.tsx — ends with an unclosed JSX element so esbuild inside `vite build`
 * emits "[ERROR] Unexpected end of file in JSX expression".
 * The `run_build_command` error-detection looks for "error" in output (case-insensitive),
 * so this reliably triggers the executor's auto-fix step.
 */
const APP_TSX_FAULTY = `import { useState } from 'react'
import './index.css'

interface Todo { id: number; text: string; done: boolean }

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState<string>('')

  return (
    <div className="app">
      <h1>Todo App</h1>
      {/* e2e-intentional-jsx-error: unclosed element below breaks vite build */}
      <incomplete-e2e-build-error-element

interface Todo {
  id: number
  text: string
  done: boolean
}

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState<string>('')

  const add = (): void => {
    if (!input.trim()) return
    setTodos(prev => [...prev, { id: Date.now(), text: input.trim(), done: false }])
    setInput('')
  }

  const toggle = (id: number): void =>
    setTodos(prev => prev.map(t => (t.id === id ? { ...t, done: !t.done } : t)))

  const remove = (id: number): void =>
    setTodos(prev => prev.filter(t => t.id !== id))

  return (
    <div className="app">
      <h1>Todo App</h1>
      <div className="input-row">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="Add todo..."
        />
        <button onClick={add}>Add</button>
      </div>
      <ul>
        {todos.map(t => (
          <li key={t.id} className={t.done ? 'done' : ''}>
            <span onClick={() => toggle(t.id)}>{t.text}</span>
            <button onClick={() => remove(t.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}`;

const INDEX_CSS_CONTENT = `body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #f0f2f5;
}
.app { max-width: 480px; margin: 40px auto; background: white; border-radius: 8px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,.1); }
h1 { margin: 0 0 16px; color: #1a1a2e; font-size: 22px; }
.input-row { display: flex; gap: 8px; margin-bottom: 16px; }
input { flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; outline: none; }
input:focus { border-color: #4f46e5; }
button { padding: 8px 16px; background: #4f46e5; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
button:hover { background: #4338ca; }
ul { list-style: none; padding: 0; margin: 0; }
li { display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f2f5; gap: 8px; }
li span { flex: 1; cursor: pointer; font-size: 14px; }
li.done span { text-decoration: line-through; color: #999; }
li button { padding: 4px 8px; background: #ef4444; font-size: 12px; }
li button:hover { background: #dc2626; }`;

/**
 * Dark mode App.tsx — intentionally BUGGY: useEffect fires console.error on mount.
 * The template's index.html forwards console.error via postMessage → ErrorToast → Fix with AI.
 */
const DARK_MODE_APP_TSX_BUGGY = `import { useState, useEffect } from 'react'
import './index.css'

interface Todo {
  id: number
  text: string
  done: boolean
}

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState<string>('')
  const [dark, setDark] = useState<boolean>(false)

  // e2e-followup-bug: setTimeout throw → window.onerror → ErrorToast → "Fix with AI"
  useEffect(() => { const t = setTimeout(() => { throw new Error('E2E Followup Bug: dark mode introduced a bug') }, 200); return () => clearTimeout(t) }, [])

  const add = (): void => {
    if (!input.trim()) return
    setTodos(prev => [...prev, { id: Date.now(), text: input.trim(), done: false }])
    setInput('')
  }

  const toggle = (id: number): void =>
    setTodos(prev => prev.map(t => (t.id === id ? { ...t, done: !t.done } : t)))

  const remove = (id: number): void =>
    setTodos(prev => prev.filter(t => t.id !== id))

  return (
    <div className={\`app \${dark ? 'dark' : ''}\`}>
      <div className="app-header">
        <h1>Todo App</h1>
        <button className="theme-btn" onClick={() => setDark(d => !d)} title="Toggle dark mode">
          {dark ? '☀️' : '🌙'}
        </button>
      </div>
      <div className="input-row">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} placeholder="Add todo..." />
        <button onClick={add}>Add</button>
      </div>
      <ul>
        {todos.map(t => (
          <li key={t.id} className={t.done ? 'done' : ''}>
            <span onClick={() => toggle(t.id)}>{t.text}</span>
            <button onClick={() => remove(t.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}`;

/** Dark mode App.tsx — FIXED (no bug, used by FixErrorAgent response [13]). */
const DARK_MODE_APP_TSX_FIXED = `import { useState } from 'react'
import './index.css'

interface Todo {
  id: number
  text: string
  done: boolean
}

export default function App() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [input, setInput] = useState<string>('')
  const [dark, setDark] = useState<boolean>(false)

  const add = (): void => {
    if (!input.trim()) return
    setTodos(prev => [...prev, { id: Date.now(), text: input.trim(), done: false }])
    setInput('')
  }

  const toggle = (id: number): void =>
    setTodos(prev => prev.map(t => (t.id === id ? { ...t, done: !t.done } : t)))

  const remove = (id: number): void =>
    setTodos(prev => prev.filter(t => t.id !== id))

  return (
    <div className={\`app \${dark ? 'dark' : ''}\`}>
      <div className="app-header">
        <h1>Todo App</h1>
        <button className="theme-btn" onClick={() => setDark(d => !d)} title="Toggle dark mode">
          {dark ? '☀️' : '🌙'}
        </button>
      </div>
      <div className="input-row">
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && add()} placeholder="Add todo..." />
        <button onClick={add}>Add</button>
      </div>
      <ul>
        {todos.map(t => (
          <li key={t.id} className={t.done ? 'done' : ''}>
            <span onClick={() => toggle(t.id)}>{t.text}</span>
            <button onClick={() => remove(t.id)}>✕</button>
          </li>
        ))}
      </ul>
    </div>
  )
}`;

// ---------------------------------------------------------------------------
// Project summary JSON
// ---------------------------------------------------------------------------
const PROJECT_SUMMARY_JSON = JSON.stringify({
  summary: 'A clean todo app built with React and TypeScript. Add, complete, and delete tasks.',
  tech_stack: ['React 18', 'TypeScript', 'Vite', 'CSS'],
  features: ['Add new todos', 'Toggle completion status', 'Delete todos'],
  file_overview: {
    'src/App.tsx': 'Main component with todo state and CRUD operations',
    'src/index.css': 'App layout and todo item styles',
  },
});

// ---------------------------------------------------------------------------
// Helper: build a flowArtifact XML for a single file response
// ---------------------------------------------------------------------------
function fileXml(path: string, content: string): string {
  return `<flowArtifact id="fix" title="Fix">\n<flowAction type="file" filePath="${path}">\n${content}\n</flowAction>\n</flowArtifact>`;
}

// ---------------------------------------------------------------------------
// Exported queue — seed the mock server with this before the test
// ---------------------------------------------------------------------------
export const FULL_FLOW_QUEUE: QueuedResponse[] = [
  // ── First plan attempt ───────────────────────────────────────────────────
  // [0] PlanAgent: architecture (parallel call 1)
  { content: DESIGN_JSON },

  // [1] PlanAgent: UX design (parallel call 2)
  { content: DESIGN_JSON },

  // [2] PlanAgent: first user plan overview
  { content: PLAN_OVERVIEW_JSON },

  // ── Plan rejection retry (user clicks "Start over") ──────────────────────
  // PlanAgent re-runs from scratch; needs fresh design + overview calls.
  // [3] PlanAgent: architecture (rejection retry, parallel call 1)
  { content: DESIGN_JSON },

  // [4] PlanAgent: UX design (rejection retry, parallel call 2)
  { content: DESIGN_JSON },

  // [5] PlanAgent: plan overview after rejection retry
  { content: PLAN_OVERVIEW_JSON },

  // ── Modify + approve ─────────────────────────────────────────────────────
  // [6] PlanAgent: modified plan overview (user clicks "Change something" + sends feedback)
  { content: PLAN_OVERVIEW_MODIFIED_JSON },

  // ── Execute ──────────────────────────────────────────────────────────────
  // [7] ExecuteAgent: technical work plan
  { content: WORK_PLAN_JSON },

  // [8] ExecuteAgent: task-1 streaming codegen → FAULTY App.tsx (TS type error)
  { content: fileXml('src/App.tsx', APP_TSX_FAULTY) },

  // [9] ExecuteAgent: task-2 streaming codegen → clean index.css
  { content: fileXml('src/index.css', INDEX_CSS_CONTENT) },

  // [10] ExecuteAgent: auto-fix attempt (executor finds TS error, calls stream_chat to fix)
  { content: fileXml('src/App.tsx', APP_TSX_CLEAN) },

  // [11] ExecuteAgent: project summary
  { content: PROJECT_SUMMARY_JSON },

  // [12] FixErrorAgent: user-introduced bug fix
  { content: fileXml('src/App.tsx', APP_TSX_CLEAN) },

  // [13] FixErrorAgent: runtime crash button fix
  { content: fileXml('src/App.tsx', APP_TSX_CLEAN) },

  // [14] FollowUpAgent: write BUGGY dark mode App.tsx via tool call
  {
    tool_calls: [
      {
        id: 'call_dark_mode',
        type: 'function',
        function: {
          name: 'write_file',
          arguments: JSON.stringify({
            path: 'src/App.tsx',
            content: DARK_MODE_APP_TSX_BUGGY,
          }),
        },
      },
    ],
  },

  // [15] FollowUpAgent: final text answer
  {
    content:
      "I've added a dark mode toggle (🌙/☀️) to the header. Click it to switch between light and dark themes.",
  },

  // [16] FixErrorAgent: fix the bug introduced by the followup (removes _followupBug line)
  { content: fileXml('src/App.tsx', DARK_MODE_APP_TSX_FIXED) },
];
