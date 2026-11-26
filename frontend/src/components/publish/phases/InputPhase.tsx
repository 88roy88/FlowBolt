import { ReactNode, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Pencil } from 'lucide-react';
import { DialogTitle } from '../../../components/ui/dialog';
import { SlugInput } from '../components/SlugInput';
import { SlugPreview } from '../components/SlugPreview';
import { PublishButton } from '../components/PublishButton';
import { PublishDetailsFields } from '../components/PublishDetailsFields';
import { BTN_SECONDARY } from '../styles';
import { usePublishStore } from '../../../stores/publish';
import { useSlugAvailability, SlugStatus } from '../../../hooks/useSlugAvailability';
import { useClientConfigQuery } from '../../../hooks/useClientConfig';
import type { PublishDetails } from '../../../types';

interface InputPhaseProps {
  isPublishing: boolean;
  onPublish: (useSlug: boolean, details: PublishDetails) => void;
}

export function InputPhase({ isPublishing, onPublish }: InputPhaseProps) {
  const mode = usePublishStore(s => s.mode);
  const projectId = usePublishStore(s => s.projectId);
  const slug = usePublishStore(s => s.slug);
  const initialSlug = usePublishStore(s => s.initialSlug);
  const onSlugChange = usePublishStore(s => s.setSlug);
  const onCancelEditing = usePublishStore(s => s.resetSlug);
  const isChanged = usePublishStore(s => s.isChanged());
  const { status: slugStatus, canPublish } = useSlugAvailability();
  const appType = usePublishStore(s => s.appType);
  const appDescription = usePublishStore(s => s.appDescription);
  const publishReason = usePublishStore(s => s.publishReason);
  const clientConfig = useClientConfigQuery();
  const publishForm = clientConfig.data?.publish_form;

  const { t } = useTranslation();
  const [isEditingSlug, setIsEditingSlug] = useState(mode === 'create');
  
  const isEditMode = mode === 'edit';
  const hasAppType = !!publishForm?.app_types.some((type) => type.id === appType);
  const submitDisabled = isPublishing || !hasAppType;

  const publish = (useSlug: boolean) => onPublish(useSlug, {
    app_type: appType,
    app_description: appDescription.trim() || null,
    publish_reason: publishForm?.publish_reasons.includes(publishReason) ? publishReason : null,
  });
  const showHint = isEditMode ? (!!slug && slug !== initialSlug) : !!slug;
  const isUrlConfirmed = showHint ? slugStatus === 'available' : isEditMode && !!slug;

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
      <SlugPreview slugValue={slug || t('publish.slugPlaceholder')} dimmed={!isUrlConfirmed} />
    </div>
  );

  return (
    <div className="flex flex-col space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full flex items-center justify-center bg-primary/10 shrink-0">
          <Globe className="w-5 h-5 text-primary" />
        </div>
        <div>
          <DialogTitle className="text-lg font-semibold tracking-tight">
            {isEditMode ? t('publish.republishTitle') : t('publish.publishTitle')}
          </DialogTitle>
          <p className="text-xs text-muted-foreground">
            {isEditMode ? t('publish.republishSubtitle') : t('publish.publishSubtitle')}
          </p>
        </div>
      </div>

      {/* Edit mode — read-only */}
      {isEditMode && !isEditingSlug && (
        <>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-foreground">{t('publish.currentUrl')}</label>
            <SlugPreview slugValue={initialSlug || projectId || ''} />
          </div>

          <PublishDetailsFields clientConfig={clientConfig} disabled={isPublishing} />

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
              disabled={submitDisabled}
              onClick={() => publish(true)}
              label={isPublishing ? t('publish.publishing') : t('publish.republish')}
            />
          </div>
        </>
      )}

      {/* Editing or Create mode */}
      {( (!isEditMode) || (isEditMode && isEditingSlug) ) && (
        <>
          {renderSlugField()}

          <PublishDetailsFields clientConfig={clientConfig} disabled={isPublishing} />

          {isEditMode && (
            <p className={`text-xs text-amber-500/90 ${isChanged ? '' : 'invisible'}`}>{t('publish.slugChangeWarning')}</p>
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
                onClick={() => publish(false)}
                disabled={submitDisabled}
                className={`flex-1 ${BTN_SECONDARY}`}
              >
                {t('publish.skipSlug')}
              </button>
            )}
            
            <PublishButton
              publishing={isPublishing}
              disabled={submitDisabled || !canPublish}
              onClick={() => publish(true)}
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
