import { useRef, useCallback, useState, useEffect } from 'react';
import { Globe, Loader2 } from 'lucide-react';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Preview } from '../preview/Preview';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { publishToS3 } from '../../services/api';

type RightTab = 'preview' | 'code';

const MAIN_SPLIT_MIN = 0.2;
const MAIN_SPLIT_MAX = 0.8;

export function ClassicLayout() {
  const [rightTab, setRightTab] = useState<RightTab>('preview');
  const [mainSplit, setMainSplit] = useState(0.4);
  const mainTopRef = useRef<HTMLDivElement>(null);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const sessionId = useSessionStore((s) => s.sessionId);
  const [isPublishing, setIsPublishing] = useState(false);

  const handlePublish = useCallback(async () => {
    if (!sessionId || isPublishing) return;
    setIsPublishing(true);
    try {
      const result = await publishToS3(sessionId);
      window.open(result.url, '_blank');
    } catch (err) {
      alert(`Publish failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      setIsPublishing(false);
    }
  }, [sessionId, isPublishing]);

  useEffect(() => {
    if (agentPhase === 'executing' || agentPhase === 'complete') {
      setRightTab('preview');
    }
  }, [agentPhase]);

  const handleMainSplitResize = useCallback((delta: number) => {
    const el = mainTopRef.current;
    if (!el) return;
    const width = el.getBoundingClientRect().width;
    if (width <= 0) return;
    setMainSplit((s) => Math.min(MAIN_SPLIT_MAX, Math.max(MAIN_SPLIT_MIN, s + delta / width)));
  }, []);

  return (
    <div ref={mainTopRef} className="flex-1 min-h-0 flex flex-row overflow-hidden relative">
      <div style={{ flex: mainSplit, minWidth: 0 }} className="min-h-0 h-full overflow-hidden">
        <ChatPanel />
      </div>

      <Resizer direction="horizontal" onDrag={handleMainSplitResize} />

      <div style={{ flex: 1 - mainSplit, minWidth: 0 }} className="overflow-hidden flex flex-col">
        <div className="flex items-center border-b border-border bg-surface shrink-0">
          {(['preview', 'code'] as RightTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setRightTab(tab)}
              className={`px-4 py-2 text-[13px] font-medium border-b-2 transition-colors duration-150 capitalize ${
                rightTab === tab
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {tab}
            </button>
          ))}

          <div className="ml-auto pr-2">
            <button
              title="Publish to S3"
              disabled={!sessionId || isPublishing}
              onClick={handlePublish}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all duration-150 ${
                sessionId && !isPublishing
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer shadow-sm'
                  : 'bg-muted text-muted-foreground opacity-50 cursor-not-allowed'
              }`}
            >
              {isPublishing ? <Loader2 size={13} className="animate-spin" /> : <Globe size={13} />}
              {isPublishing ? 'Publishing...' : 'Publish'}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          {rightTab === 'preview' ? <Preview /> : <EditorPanel />}
        </div>
      </div>
    </div>
  );
}
