import { Dialog, DialogContent, DialogClose } from '../ui/dialog';
import { usePublishStore } from '../../stores/publish';
import { usePublishMutation } from '../../hooks/usePublishMutation';
import { InputPhase } from './phases/InputPhase';
import { SuccessPhase } from './phases/SuccessPhase';
import { ErrorPhase } from './phases/ErrorPhase';

export function PublishModal() {
  const isOpen = usePublishStore(s => s.isOpen);
  const closeModal = usePublishStore(s => s.close);
  const projectId = usePublishStore(s => s.projectId);
  const publish = usePublishMutation(projectId);

  if (!isOpen) return null;

  const handleClose = () => {
    publish.reset();
    closeModal();
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="w-[448px] p-0 pb-10 border-border/60 bg-surface/95 backdrop-blur-xl min-h-[260px] flex flex-col transition-all duration-300 ease-in-out">
        <DialogClose onClose={handleClose} />

        <div className="flex-1 flex flex-col pt-10 pb-0 px-6">
          {publish.isError ? (
            <ErrorPhase errorMessage={publish.error.message} onClose={handleClose} />
          ) : publish.isSuccess ? (
            <SuccessPhase resultUrl={publish.data.url} onClose={handleClose} />
          ) : (
            <InputPhase
              isPublishing={publish.isPending}
              onPublish={(useSlug) => publish.mutate({ useSlug })}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
