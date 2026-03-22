import { useEffect, useState } from 'react';
import { useChatStore } from '../../stores/chat';

export function GlobalProgress() {
  const agentPhase = useChatStore((s) => s.agentPhase);
  const tasks = useChatStore((s) => s.executionTasks);
  const [visible, setVisible] = useState(false);

  const progress =
    agentPhase === 'idle' ? 0 :
    agentPhase === 'classifying' ? 5 :
    agentPhase === 'fetching_cases' ? 10 :
    agentPhase === 'designing' ? 15 :
    agentPhase === 'planning' ? 30 :
    agentPhase === 'awaiting_approval' ? 35 :
    agentPhase === 'executing' ? 40 + (tasks.filter((t) => t.status === 'completed').length / Math.max(tasks.length, 1)) * 55 :
    agentPhase === 'fixing' ? 50 :
    agentPhase === 'exploring' ? 50 :
    agentPhase === 'complete' ? 100 : 0;

  // Show when active, hide after completion with a brief delay
  useEffect(() => {
    if (progress > 0 && progress < 100) {
      setVisible(true);
    } else if (progress === 100) {
      const timer = setTimeout(() => setVisible(false), 1500);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [progress]);

  if (!visible && progress !== 100) return null;
  if (!visible) return null;

  return (
    <div className={`h-0.5 w-full shrink-0 overflow-hidden transition-opacity duration-500 ${progress === 100 ? 'opacity-0' : 'opacity-100'}`}>
      <div
        className={`h-full transition-all duration-700 ease-out ${
          progress < 100 ? 'progress-bar-shimmer' : 'bg-success'
        }`}
        style={{ width: `${progress}%` }}
      />
    </div>
  );
}
