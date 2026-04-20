import { Dialog, DialogContent, DialogClose } from '../ui/dialog';
import { usePublishLogic } from './usePublishLogic';
import { InputPhase } from './phases/InputPhase';
import { SuccessPhase } from './phases/SuccessPhase';
import { ErrorPhase } from './phases/ErrorPhase';

interface PublishModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  existingHandle?: string;
  mode?: 'create' | 'edit';
  onPublish: (slug: string | undefined) => Promise<void>;
  resultUrl?: string;
  errorMessage?: string;
}

export function PublishModal({
  open,
  onOpenChange,
  projectId,
  existingHandle,
  mode = 'create',
  onPublish,
  resultUrl,
  errorMessage,
}: PublishModalProps) {
  // If handle matches projectId, it's the default handle (no custom slug)
  const isDefaultHandle = existingHandle === projectId;
  const initialSlug = isDefaultHandle ? '' : (existingHandle ?? '');

  const {
    slug,
    slugStatus,
    isPublishing,
    handleSlugChange,
    handlePublish,
    resetSlug,
    canPublish,
    isChanged
  } = usePublishLogic({ projectId, initialSlug, onPublish });

  // Phase derivation
  // SuccessPhase handles its own display.

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[448px] p-0 pb-10 border-border/60 bg-surface/95 backdrop-blur-xl min-h-[260px] flex flex-col transition-all duration-300 ease-in-out">
        <DialogClose onClose={() => onOpenChange(false)} />

        <div className="flex-1 flex flex-col pt-10 pb-0 px-6">
          {errorMessage ? (
            <ErrorPhase errorMessage={errorMessage} onClose={() => onOpenChange(false)} />
          ) : resultUrl ? (
            <SuccessPhase resultUrl={resultUrl} onClose={() => onOpenChange(false)} />
          ) : (
            <InputPhase
              mode={mode}
              slug={slug}
              slugStatus={slugStatus}
              isPublishing={isPublishing}
              canPublish={canPublish}
              isChanged={isChanged}
              existingHandle={existingHandle}
              initialSlug={initialSlug}
              onSlugChange={handleSlugChange}
              onPublish={handlePublish}
              onCancelEditing={resetSlug}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
