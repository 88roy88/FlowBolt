import { CheckCircle2, XCircle } from 'lucide-react';
import type { ExecutionTask } from '../../../types';
import { CardWrapper } from './CardWrapper';

export function TaskProgressCard({ tasks }: { tasks: ExecutionTask[] }) {
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;
  const total = tasks.length;

  return (
    <CardWrapper>
      <div className={`flex items-center gap-1.5 mb-2 text-xs ${failed > 0 ? 'text-destructive' : 'text-success'}`}>
        {failed > 0 ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
        {failed > 0 ? `Built ${completed}/${total} tasks (${failed} failed)` : `Built ${completed}/${total} tasks`}
      </div>
      <div className="flex flex-col gap-0.5">
        {tasks.map((task) => (
          <div key={task.id} className="flex items-center gap-1.5 text-xs">
            {task.status === 'completed' ? (
              <CheckCircle2 size={11} className="text-success shrink-0" />
            ) : task.status === 'failed' ? (
              <XCircle size={11} className="text-destructive shrink-0" />
            ) : (
              <span className="w-[11px] h-[11px] shrink-0" />
            )}
            <span className={task.status === 'failed' ? 'text-destructive' : ''}>{task.title}</span>
          </div>
        ))}
      </div>
    </CardWrapper>
  );
}
