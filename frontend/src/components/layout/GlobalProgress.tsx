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
    agentPhase === AGENT_PHASE.idle ? 3 :
    agentPhase === AGENT_PHASE.fetching_data_sources ? 10 :
    agentPhase === AGENT_PHASE.designing ? 15 :
    agentPhase === AGENT_PHASE.planning ? 30 :
    agentPhase === AGENT_PHASE.awaiting_approval ? 35 :
    agentPhase === AGENT_PHASE.executing ? 40 + (tasks.filter((t) => t.status === 'completed').length / Math.max(tasks.length, 1)) * 55 :
    agentPhase === AGENT_PHASE.fixing ? 50 :
    agentPhase === AGENT_PHASE.exploring ? 50 :
    agentPhase === AGENT_PHASE.complete ? 100 : 0;

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
