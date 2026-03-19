import { CheckCircle2, XCircle } from 'lucide-react';
import type { ExecutionTask } from '../../../types';
import { CardWrapper } from './CardWrapper';

export function TaskProgressCard({ tasks }: { tasks: ExecutionTask[] }) {
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;
  const total = tasks.length;

  return (
    <CardWrapper>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '8px',
        fontSize: '12px',
        color: failed > 0 ? 'var(--danger)' : 'var(--success)',
      }}>
        {failed > 0 ? <XCircle size={12} /> : <CheckCircle2 size={12} />}
        {failed > 0
          ? `Built ${completed}/${total} tasks (${failed} failed)`
          : `Built ${completed}/${total} tasks`}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        {tasks.map((task) => (
          <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
            {task.status === 'completed' ? (
              <CheckCircle2 size={11} style={{ color: 'var(--success)', flexShrink: 0 }} />
            ) : task.status === 'failed' ? (
              <XCircle size={11} style={{ color: 'var(--danger)', flexShrink: 0 }} />
            ) : (
              <span style={{ width: 11, height: 11, flexShrink: 0 }} />
            )}
            <span style={{ color: task.status === 'failed' ? 'var(--danger)' : 'var(--text)' }}>
              {task.title}
            </span>
          </div>
        ))}
      </div>
    </CardWrapper>
  );
}
