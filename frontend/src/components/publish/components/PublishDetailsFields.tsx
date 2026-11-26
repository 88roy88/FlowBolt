import { useTranslation } from 'react-i18next';
import { Textarea } from '../../ui/textarea';
import { LoadingDots } from '../../ui/loading-dots';
import { AppTypePicker } from './AppTypePicker';
import { usePublishStore } from '../../../stores/publish';
import type { useClientConfigQuery } from '../../../hooks/useClientConfig';

interface PublishDetailsFieldsProps {
  clientConfig: ReturnType<typeof useClientConfigQuery>;
  disabled: boolean;
}

export function PublishDetailsFields({ clientConfig, disabled }: PublishDetailsFieldsProps) {
  const appType = usePublishStore(s => s.appType);
  const appDescription = usePublishStore(s => s.appDescription);
  const publishReason = usePublishStore(s => s.publishReason);
  const setAppType = usePublishStore(s => s.setAppType);
  const setAppDescription = usePublishStore(s => s.setAppDescription);
  const setPublishReason = usePublishStore(s => s.setPublishReason);
  const { t } = useTranslation();

  if (!clientConfig.data) {
    return clientConfig.isError ? (
      <div role="alert" className="flex items-center gap-2 text-xs text-destructive">
        {t('publish.formLoadFailed')}
        <button type="button" onClick={() => clientConfig.refetch()} className="underline">
          {t('common.retry')}
        </button>
      </div>
    ) : (
      <p className="py-4 text-center text-xs text-muted-foreground"><LoadingDots /></p>
    );
  }

  const { publish_form: publishForm, app_description_max_chars: descriptionMaxChars } = clientConfig.data;
  const optional = <span className="font-normal text-muted-foreground">({t('publish.optional')})</span>;

  return (
    <div className="space-y-4">
      <AppTypePicker
        appTypes={publishForm.app_types}
        value={appType}
        onChange={setAppType}
        label={t('publish.appTypeLabel')}
        disabled={disabled}
      />

      <div className="space-y-1.5">
        <label htmlFor="publish-app-description" className="text-sm font-medium text-foreground">
          {t('publish.descriptionLabel')} {optional}
        </label>
        <Textarea
          id="publish-app-description"
          value={appDescription}
          onChange={(e) => setAppDescription(e.target.value)}
          placeholder={t('publish.descriptionPlaceholder')}
          maxLength={descriptionMaxChars}
          rows={2}
          // Follow the typed text's direction; while empty, the placeholder follows the UI's.
          dir={appDescription ? 'auto' : undefined}
          disabled={disabled}
          className="resize-none rounded-lg border-border/60 bg-muted/30"
        />
      </div>

      {publishForm.publish_reasons.length > 0 && (
        <div className="space-y-1.5">
          <label htmlFor="publish-reason" className="text-sm font-medium text-foreground">
            {t('publish.reasonLabel')} {optional}
          </label>
          <select
            id="publish-reason"
            value={publishForm.publish_reasons.includes(publishReason) ? publishReason : ''}
            onChange={(e) => setPublishReason(e.target.value)}
            disabled={disabled}
            className="w-full rounded-lg border border-border/60 bg-surface px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
          >
            <option value="">{t('publish.reasonPlaceholder')}</option>
            {publishForm.publish_reasons.map((reason) => (
              <option key={reason} value={reason}>{reason}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
