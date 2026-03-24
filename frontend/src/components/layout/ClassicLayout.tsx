import { useRef, useCallback, useState, useEffect } from 'react';
import { Globe, Loader2 } from 'lucide-react';
import { Resizer } from './Resizer';
import { ChatPanel } from '../chat/ChatPanel';
import { EditorPanel } from '../editor/EditorPanel';
import { Preview } from '../preview/Preview';
import { useChatStore } from '../../stores/chat';
import { useSessionStore } from '../../stores/session';
import { publishToS3 } from '../../services/api';
import { PublishModal } from '../ui/PublishModal';
import { ExternalLink } from 'lucide-react';

type RightTab = 'preview' | 'code';

const MAIN_SPLIT_MIN = 0.2;
const MAIN_SPLIT_MAX = 0.8;

export function ClassicLayout() {
  const [rightTab, setRightTab] = useState<RightTab>('preview');
  const [mainSplit, setMainSplit] = useState(0.4);
  const mainTopRef = useRef<HTMLDivElement>(null);
  const agentPhase = useChatStore((s) => s.agentPhase);
  const projectId = useSessionStore((s) => s.projectId);
  const currentProject = useSessionStore((s) => s.currentProject);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishModalState, setPublishModalState] = useState<{ open: boolean; url?: string; error?: string }>({ open: false });
  
  const messages = useChatStore((s) => s.messages);
  const historyLoaded = useChatStore((s) => s.historyLoaded);
  const isNewProject = !historyLoaded || messages.length === 0;
  const isPublished = !!currentProject?.published_url;

  const handlePublish = useCallback(async () => {
    if (!projectId || isPublishing) return;
    setIsPublishing(true);
    try {
      const result = await publishToS3(projectId);
      const current = useSessionStore.getState().currentProject;
      if (current) {
        useSessionStore.getState().setProjectPublishedUrl(current.id, result.url);
      }
      setPublishModalState({ open: true, url: result.url });
    } catch (err) {
      setPublishModalState({ open: true, error: err instanceof Error ? err.message : String(err) });
    } finally {
      setIsPublishing(false);
    }
  }, [projectId, isPublishing]);

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

  if (isNewProject) {
    return (
      <div className="flex-1 min-h-0 flex flex-row overflow-hidden relative">
        <div className="flex-1 min-h-0 h-full overflow-hidden">
          <ChatPanel />
        </div>
      </div>
    );
  }

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

          <div className="ml-auto pr-2 flex items-center gap-2">
            {isPublished && projectId && (
              <a
                href={`/api/export/${projectId}/published`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all duration-150 text-primary border border-primary/20 hover:bg-primary/10 shadow-sm"
                title="View Published App"
              >
                <ExternalLink size={13} />
                View Live
              </a>
            )}
            <button
          title={isPublished ? "Republish" : "Publish to S3"}
          disabled={!projectId || isPublishing}
              onClick={handlePublish}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all duration-150 ${
                projectId && !isPublishing
                  ? 'bg-primary text-primary-foreground hover:bg-primary/90 cursor-pointer shadow-sm'
                  : 'bg-muted text-muted-foreground opacity-50 cursor-not-allowed'
              }`}
            >
              {isPublishing ? <Loader2 size={13} className="animate-spin" /> : <Globe size={13} />}
              {isPublishing ? 'Publishing...' : isPublished ? 'Republish' : 'Publish'}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          {rightTab === 'preview' ? <Preview /> : <EditorPanel />}
        </div>
      </div>
      
      <PublishModal 
        open={publishModalState.open} 
        onOpenChange={(open) => setPublishModalState(s => ({ ...s, open }))}
        url={publishModalState.url}
        errorMessage={publishModalState.error}
      />
    </div>
  );
}
