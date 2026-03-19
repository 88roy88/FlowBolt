import { CheckCircle2, Circle, Loader2, XCircle } from 'lucide-react';
import type { ExecutionTask } from '../../types';

interface TaskProgressProps {
  tasks: ExecutionTask[];
}

function TaskStatusIcon({ status }: { status: ExecutionTask['status'] }) {
  switch (status) {
    case 'pending':
      return <Circle size={16} style={{ color: 'var(--text-dim)', opacity: 0.4 }} />;
    case 'running':
      return <Loader2 size={16} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />;
    case 'completed':
      return <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />;
    case 'failed':
      return <XCircle size={16} style={{ color: 'var(--danger)' }} />;
  }
}

export function TaskProgress({ tasks }: TaskProgressProps) {
  const completed = tasks.filter((t) => t.status === 'completed').length;
  const total = tasks.length;

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '16px',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '12px',
      }}>
        <h3 style={{ fontSize: '14px', fontWeight: 600 }}>
          Building your app...
        </h3>
        <span style={{ fontSize: '12px', color: 'var(--text-dim)' }}>
          {completed}/{total}
        </span>
      </div>

      {/* Progress bar */}
      <div style={{
        height: '4px',
        background: 'var(--bg)',
        borderRadius: '2px',
        marginBottom: '14px',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${total > 0 ? (completed / total) * 100 : 0}%`,
          background: 'var(--success)',
          borderRadius: '2px',
          transition: 'width 0.3s ease',
        }} />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {tasks.map((task) => (
          <div
            key={task.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 8px',
              borderRadius: '6px',
              background: task.status === 'running' ? 'rgba(137, 180, 250, 0.08)' : 'transparent',
              fontSize: '13px',
              transition: 'background 0.2s',
            }}
          >
            <TaskStatusIcon status={task.status} />
            <span style={{
              color: task.status === 'pending' ? 'var(--text-dim)' : 'var(--text)',
              opacity: task.status === 'pending' ? 0.6 : 1,
            }}>
              {task.title}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
