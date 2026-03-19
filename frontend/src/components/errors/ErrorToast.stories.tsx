import type { Meta, StoryObj } from '@storybook/react-vite';
import { AlertTriangle, X, Wrench, RefreshCw } from 'lucide-react';
import { Button } from '../ui/button';

const meta: Meta = {
  title: 'Errors/ErrorToast',
  parameters: { layout: 'padded' },
};
export default meta;

function MockToast({ source, message, file, line }: {
  source: 'build' | 'runtime' | 'connection';
  message: string;
  file?: string;
  line?: number;
}) {
  return (
    <div className="flex items-start gap-2.5 p-3 bg-card border border-destructive rounded-lg max-w-[420px] shadow-[var(--shadow-lg)]">
      <AlertTriangle size={18} className="text-destructive shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-[11px] font-semibold text-destructive uppercase tracking-wider mb-1">
          {source === 'build' ? 'Build Error' : source === 'runtime' ? 'Runtime Error' : 'Connection Error'}
        </div>
        <div className="text-[13px] leading-snug break-words">
          {message.length > 150 ? message.slice(0, 150) + '...' : message}
        </div>
        {file && (
          <button className="block text-[11px] text-primary underline mt-1.5 text-left cursor-pointer">
            {file}{line ? `:${line}` : ''}
          </button>
        )}
        {source === 'connection' ? (
          <Button variant="outline" size="sm" className="mt-2.5 ml-auto">
            <RefreshCw size={12} /> Retry
          </Button>
        ) : (
          <Button variant="outline" size="sm" className="mt-2.5 ml-auto">
            <Wrench size={12} /> Fix with AI
          </Button>
        )}
      </div>
      <button className="p-0.5 text-muted-foreground shrink-0" title="Dismiss">
        <X size={14} />
      </button>
    </div>
  );
}

export const BuildError: StoryObj = {
  render: () => (
    <MockToast
      source="build"
      message="Cannot read properties of undefined (reading 'map')"
      file="/src/components/PeopleGrid.tsx"
      line={42}
    />
  ),
};

export const RuntimeError: StoryObj = {
  render: () => (
    <MockToast
      source="runtime"
      message="Uncaught TypeError: Cannot set property 'innerHTML' of null at main.js:15"
    />
  ),
};

export const ConnectionError: StoryObj = {
  render: () => (
    <MockToast
      source="connection"
      message="Cannot connect to backend server. Please ensure the server is running."
    />
  ),
};

export const MultipleErrors: StoryObj = {
  render: () => (
    <div className="flex flex-col gap-2">
      <MockToast source="build" message="Module not found: './utils'" file="/src/App.tsx" line={3} />
      <MockToast source="runtime" message="Uncaught ReferenceError: data is not defined" />
    </div>
  ),
};
