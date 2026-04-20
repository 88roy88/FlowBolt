import { Dialog, DialogContent, DialogClose } from '../ui/dialog';
import { usePublishStore } from '../../stores/publish';
import { InputPhase } from './phases/InputPhase';
import { SuccessPhase } from './phases/SuccessPhase';
import { ErrorPhase } from './phases/ErrorPhase';

export function PublishModal() {
  const isOpen = usePublishStore(s => s.isOpen);
  const closeModal = usePublishStore(s => s.close);
  const resultUrl = usePublishStore(s => s.resultUrl);
  const errorMessage = usePublishStore(s => s.errorMessage);
  const mode = usePublishStore(s => s.mode);
  const resetSlug = usePublishStore(s => s.resetSlug);
  const performPublish = usePublishStore(s => s.performPublish);

  if (!isOpen) return null;


  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeModal()}>
      <DialogContent className="w-[448px] p-0 pb-10 border-border/60 bg-surface/95 backdrop-blur-xl min-h-[260px] flex flex-col transition-all duration-300 ease-in-out">
        <DialogClose onClose={closeModal} />

        <div className="flex-1 flex flex-col pt-10 pb-0 px-6">
          {errorMessage ? (
            <ErrorPhase errorMessage={errorMessage} onClose={closeModal} />
          ) : resultUrl ? (
            <SuccessPhase resultUrl={resultUrl} onClose={closeModal} />
          ) : (
            <InputPhase
              mode={mode}
              onPublish={performPublish}
              onCancelEditing={resetSlug}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
