import { useEffect, useState } from 'react';
import type { AgentPhase, ExecutionTask } from '../../types';
import { useChatStore, useIsAgentWorking } from '../../stores/chat';
import { AGENT_PHASE } from '../../stores/chatAgentState';

function getAgentProgress(
  working: boolean,
  agentPhase: AgentPhase,
  tasks: ExecutionTask[],
): number {
  if (!working) return 0;

  switch (agentPhase) {
    case AGENT_PHASE.idle:
      return 0;
    case AGENT_PHASE.fetching_data_sources:
      return 10;
    case AGENT_PHASE.designing:
      return 15;
    case AGENT_PHASE.planning:
      return 30;
    case AGENT_PHASE.awaiting_approval:
      return 35;
    case AGENT_PHASE.executing: {
      const completed = tasks.filter((t) => t.status === 'completed').length;
      return 40 + (completed / Math.max(tasks.length, 1)) * 55;
    }
    case AGENT_PHASE.fixing:
    case AGENT_PHASE.exploring:
      return 50;
    case AGENT_PHASE.complete:
      return 100;
    default:
      return 0;
  }
}

export function GlobalProgress() {
  const agentPhase = useChatStore((s) => s.agentPhase);
  const tasks = useChatStore((s) => s.executionTasks);
  const [visible, setVisible] = useState(false);

  const working = useIsAgentWorking();

  const progress = getAgentProgress(working, agentPhase, tasks);

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
