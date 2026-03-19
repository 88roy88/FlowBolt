import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import type { ExecutionTask } from '../../types';
import { CardWrapper } from './cards/CardWrapper';

function TaskStatusIcon({ status }: { status: ExecutionTask['status'] }) {
  switch (status) {
    case 'pending':
      return <Circle size={16} className="text-muted-foreground opacity-40" />;
    case 'running':
      return <Loader2 size={16} className="text-primary animate-spin" />;
    case 'completed':
      return <CheckCircle2 size={16} className="text-success" />;
    case 'failed':
      return <XCircle size={16} className="text-destructive" />;
  }
}

export function TaskProgress({ tasks }: { tasks: ExecutionTask[] }) {
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const total = tasks.length;

  return (
    <CardWrapper className="p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Building your app...</h3>
        <span className="text-xs text-muted-foreground">{completed}/{total}</span>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-background rounded-sm mb-3.5 overflow-hidden">
        <div
          className={`h-full rounded-sm transition-all duration-500 ease-out ${
            completed < total ? 'progress-bar-shimmer' : 'bg-success'
          }`}
          style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        {tasks.map((task) => (
          <div
            key={task.id}
            className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-[13px] transition-colors ${
              task.status === 'running' ? 'bg-running-bg' : ''
            }`}
          >
            <TaskStatusIcon status={task.status} />
            <span className={task.status === 'pending' ? 'text-muted-foreground opacity-60' : ''}>
              {task.title}
            </span>
          </div>
        ))}
      </div>
    </CardWrapper>
  );
}
