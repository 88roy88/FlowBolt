import { ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Pencil } from 'lucide-react';
import { DialogTitle } from '../../../components/ui/dialog';
import { SlugInput } from '../components/SlugInput';
import { SlugPreview } from '../components/SlugPreview';
import { PublishButton } from '../components/PublishButton';
import { BTN_SECONDARY } from '../styles';
import { usePublishStore, SlugStatus } from '../../../stores/publish';

interface InputPhaseProps {
  mode: 'create' | 'edit';
  onPublish: (useSlug: boolean) => void;
  onCancelEditing: () => void;
}

export function InputPhase({
  mode,
  onPublish,
  onCancelEditing,
}: InputPhaseProps) {
  const slug = usePublishStore(s => s.slug);
  const slugStatus = usePublishStore(s => s.status);
  const isPublishing = usePublishStore(s => s.isPublishing);
  const initialSlug = usePublishStore(s => s.initialSlug);
  const onSlugChange = usePublishStore(s => s.setSlug);
  const canPublish = usePublishStore(s => s.canPublish());
  const isChanged = usePublishStore(s => s.isChanged());
  const { t } = useTranslation();
  const [isEditingSlug, setIsEditingSlug] = useState(mode === 'create');
  
  const isEditMode = mode === 'edit';
  const showHint = isEditMode ? (!!slug && slug !== initialSlug) : !!slug;

  const slugHintMap: Partial<Record<SlugStatus, ReactNode>> = {
    invalid: <span className="text-destructive">{t('publish.slugInvalid')}</span>,
    checking: <span className="text-muted-foreground">{t('publish.slugChecking')}</span>,
    taken: <span className="text-destructive">{t('publish.slugTaken')}</span>,
    available: <span className="text-emerald-500">{t('publish.slugAvailable')}</span>,
  };

  const renderSlugField = () => (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground">{t('publish.slugLabel')}</label>
      <SlugInput
        value={slug}
        onChange={(e) => onSlugChange(e.target.value)}
        placeholder={t('publish.slugPlaceholder')}
        disabled={isPublishing}
      />
      <div className="h-4 text-xs">
        {showHint ? (slugHintMap[slugStatus] ?? null) : null}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full flex items-center justify-center bg-primary/10 shrink-0">
          <Globe className="w-5 h-5 text-primary" />
        </div>
        <div>
          <DialogTitle className="text-lg font-semibold tracking-tight">
            {isEditMode ? t('publish.republishTitle') : t('publish.chooseSlugTitle')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {isEditMode ? t('publish.republishSubtitle') : t('publish.chooseSlugSubtitle')}
          </p>
        </div>
      </div>

      {/* Edit mode — read-only */}
      {isEditMode && !isEditingSlug && (
        <>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">{t('publish.currentUrl')}</label>
            <SlugPreview slugValue={initialSlug || usePublishStore.getState().projectId!} />
          </div>

          <p className="text-xs text-amber-500/90">{t('publish.overwriteWarning')}</p>

          <div className="flex gap-2 pt-1">
            <button
              onClick={() => setIsEditingSlug(true)}
              disabled={isPublishing}
              className={BTN_SECONDARY}
            >
              <Pencil size={13} />
              {t('publish.changeUrl')}
            </button>
            <PublishButton
              publishing={isPublishing}
              disabled={isPublishing}
              onClick={() => onPublish(true)}
              label={isPublishing ? t('publish.publishing') : t('publish.republish')}
            />
          </div>
        </>
      )}

      {/* Editing or Create mode */}
      {( (!isEditMode) || (isEditMode && isEditingSlug) ) && (
        <>
          {renderSlugField()}

          {showHint && slugStatus === 'available' && (
            <SlugPreview slugValue={slug} />
          )}

          {isEditMode && isChanged && (
            <p className="text-xs text-amber-500/90">{t('publish.slugChangeWarning')}</p>
          )}

          <div className="flex gap-2 pt-1">
            {isEditMode ? (
              <button
                onClick={() => {
                  onCancelEditing();
                  setIsEditingSlug(false);
                }}
                disabled={isPublishing}
                className={BTN_SECONDARY}
              >
                {t('publish.cancelChange')}
              </button>
            ) : (
              <button
                onClick={() => onPublish(false)}
                disabled={isPublishing}
                className={`flex-1 ${BTN_SECONDARY}`}
              >
                {t('publish.skipSlug')}
              </button>
            )}
            
            <PublishButton
              publishing={isPublishing}
              disabled={isPublishing || !canPublish}
              onClick={() => onPublish(true)}
              label={
                isPublishing 
                  ? t('publish.publishing') 
                  : isEditMode 
                    ? (isChanged ? t('publish.republishWithNewSlug') : t('publish.republish'))
                    : t('publish.publishWithSlug')
              }
            />
          </div>
        </>
      )}
    </div>
  );
}
