import { useEffect, useState } from 'react';
import { useChatStore, useIsAgentWorking } from '../../stores/chat';
import { AGENT_PHASE } from '../../stores/chatAgentState';

export function GlobalProgress() {
  const agentPhase = useChatStore((s) => s.agentPhase);
  const tasks = useChatStore((s) => s.executionTasks);
  const [visible, setVisible] = useState(false);

  const working = useIsAgentWorking();

  const progress =
    !working ? 0 :
    agentPhase === AGENT_PHASE.IDLE ? 3 :
    agentPhase === AGENT_PHASE.FETCHING_DATA_SOURCES ? 10 :
    agentPhase === AGENT_PHASE.DESIGNING ? 15 :
    agentPhase === AGENT_PHASE.PLANNING ? 30 :
    agentPhase === AGENT_PHASE.AWAITING_APPROVAL ? 35 :
    agentPhase === AGENT_PHASE.EXECUTING ? 40 + (tasks.filter((t) => t.status === 'completed').length / Math.max(tasks.length, 1)) * 55 :
    agentPhase === AGENT_PHASE.FIXING ? 50 :
    agentPhase === AGENT_PHASE.EXPLORING ? 50 :
    agentPhase === AGENT_PHASE.COMPLETE ? 100 : 0;

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
