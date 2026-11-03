import { useTranslation } from 'react-i18next';
import { AlertCircle, FileText, Loader2, X } from 'lucide-react';
import { useChatStore } from '../../stores/chat';
import type { PendingAttachment } from '../../stores/chat';

function AttachmentChip({ attachment }: { attachment: PendingAttachment }) {
  const { t } = useTranslation();
  const removeAttachment = useChatStore((s) => s.removeAttachment);
  const failed = attachment.status === 'failed';
  const uploading = attachment.status === 'uploading';
  const title = failed ? t('chat.attachment.failedShort') : uploading ? t('chat.attachment.uploading') : attachment.name;

  return (
    <div
      className={`relative flex items-center gap-1.5 h-10 rounded-lg border bg-background ps-1 pe-6 max-w-[180px] ${
        failed ? 'border-destructive/60' : 'border-border'
      }`}
      title={title}
      data-testid="pending-attachment"
    >
      {attachment.previewUrl ? (
        <img src={attachment.previewUrl} alt="" className="w-8 h-8 rounded object-cover shrink-0" />
      ) : (
        <FileText size={16} className="text-muted-foreground shrink-0 ms-1" />
      )}
      <span className="text-xs truncate" dir="auto">{attachment.name}</span>
      {uploading && (
        <span className="absolute inset-0 rounded-lg bg-background/60 flex items-center justify-center">
          <Loader2 size={14} className="animate-spin text-primary" />
        </span>
      )}
      {failed && <AlertCircle size={14} className="text-destructive shrink-0" />}
      {uploading && (
        <span
          className="absolute bottom-0 start-0 h-0.5 bg-primary rounded-full transition-[width]"
          style={{ width: `${Math.round(attachment.progress * 100)}%` }}
        />
      )}
      <button
        onClick={() => removeAttachment(attachment.localId)}
        className="absolute top-0.5 end-0.5 flex items-center justify-center w-4 h-4 rounded-sm hover:bg-muted"
        title={t('chat.attachment.remove')}
      >
        <X size={12} />
      </button>
    </div>
  );
}

export function PendingAttachments() {
  const attachments = useChatStore((s) => s.pendingAttachments);
  if (attachments.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5 px-1">
      {attachments.map((a) => <AttachmentChip key={a.localId} attachment={a} />)}
    </div>
  );
}
