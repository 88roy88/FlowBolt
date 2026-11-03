import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { FileText } from 'lucide-react';
import type { ChatAttachment } from '../../types';
import { attachmentContentUrl } from '../../services/api';
import { useSessionStore } from '../../stores/session';
import { attachmentKind } from '../../utils/attachments';
import { Dialog, DialogClose, DialogContent } from '../ui/dialog';

export function MessageAttachments({ attachments }: { attachments: ChatAttachment[] }) {
  const { t } = useTranslation();
  const projectId = useSessionStore((s) => s.projectId);
  const [enlarged, setEnlarged] = useState<ChatAttachment | null>(null);
  if (!projectId) return null;
  const url = (a: ChatAttachment) => attachmentContentUrl(projectId, a.id);

  return (
    <div className="flex flex-wrap gap-1.5 mb-1.5">
      {attachments.map((a) =>
        attachmentKind(a.content_type, a.name) === 'image' ? (
          <button
            key={a.id}
            onClick={() => setEnlarged(a)}
            className="rounded-md overflow-hidden border border-border hover:border-primary/60"
            title={t('chat.attachment.open', { name: a.name })}
          >
            <img src={url(a)} alt={a.name} loading="lazy" className="h-16 max-w-[160px] object-cover" />
          </button>
        ) : (
          <a
            key={a.id}
            href={url(a)}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 h-8 px-2 rounded-md border border-border bg-background text-xs hover:border-primary/60 max-w-[200px]"
            title={t('chat.attachment.open', { name: a.name })}
          >
            <FileText size={14} className="text-muted-foreground shrink-0" />
            <span className="truncate" dir="auto">{a.name}</span>
          </a>
        ),
      )}
      <Dialog open={enlarged !== null} onOpenChange={(open) => { if (!open) setEnlarged(null); }}>
        {enlarged && (
          <DialogContent className="max-w-[90vw] max-h-[90vh] p-2">
            <DialogClose onClose={() => setEnlarged(null)} />
            <img src={url(enlarged)} alt={enlarged.name} className="max-w-full max-h-[85vh] object-contain" />
          </DialogContent>
        )}
      </Dialog>
    </div>
  );
}
