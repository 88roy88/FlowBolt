import { useState, useRef, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Dialog, DialogContent, DialogTitle, DialogClose } from './dialog';
import { Copy, ExternalLink, Check, AlertCircle, Globe, Loader2, Pencil } from 'lucide-react';
import { checkSlugAvailability } from '../../services/api';

type SlugStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

interface PublishModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  existingSlug?: string;
  mode?: 'create' | 'edit';
  onPublish: (slug: string | undefined) => Promise<void>;
  resultUrl?: string;
  errorMessage?: string;
}

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

const BTN_SECONDARY = 'px-4 py-2.5 rounded-lg border border-border hover:bg-muted/50 transition-colors text-sm font-medium disabled:opacity-50';
const BTN_PRIMARY = 'flex-1 px-4 py-2.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground transition-colors text-sm font-medium flex justify-center items-center gap-2 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed';

// ── Tiny internal helpers (no extra files, zero behavior change) ─────────────

function SlugInput({ value, onChange, placeholder, disabled }: {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  disabled: boolean;
}) {
  return (
    <div className="flex items-center gap-0 rounded-lg border border-border/60 bg-muted/30 overflow-hidden focus-within:ring-1 focus-within:ring-primary/40">
      <span className="px-3 py-2 text-sm text-muted-foreground border-r border-border/40 bg-muted/50 shrink-0 select-none">
        /share/
      </span>
      <input
        type="text"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        disabled={disabled}
        className="flex-1 px-3 py-2 text-sm bg-transparent outline-none placeholder:text-muted-foreground/50"
        autoFocus
      />
    </div>
  );
}

function SlugPreview({ slugValue }: { slugValue: string }) {
  return (
    <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/30 border border-border/40 text-xs text-muted-foreground font-mono">
      <ExternalLink size={12} className="shrink-0" />
      <span className="truncate">{window.location.origin}/api/share/{slugValue}</span>
    </div>
  );
}

function PrimaryButton({ disabled, onClick, children }: {
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button onClick={onClick} disabled={disabled} className={BTN_PRIMARY}>
      {children}
    </button>
  );
}

function PublishButtonContent({ publishing, label }: { publishing: boolean; label: string }) {
  if (publishing) return <><Loader2 size={14} className="animate-spin" />{label}</>;
  return <><Globe size={14} />{label}</>;
}

// ── Main component ───────────────────────────────────────────────────────────

export function PublishModal({
  open,
  onOpenChange,
  projectId,
  existingSlug,
  mode = 'create',
  onPublish,
  resultUrl,
  errorMessage,
}: PublishModalProps) {
  const { t } = useTranslation();
  const [isPublishing, setIsPublishing] = useState(false);
  const [slug, setSlug] = useState(existingSlug ?? '');
  const [slugStatus, setSlugStatus] = useState<SlugStatus>('idle');
  const [copied, setCopied] = useState(false);
  const [isEditingSlug, setIsEditingSlug] = useState(mode === 'create');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Phase derivation (first truthy condition wins)
  const phase = errorMessage ? 'error'
    : resultUrl ? 'success'
    : isPublishing ? 'publishing'
    : 'input';

  const isEditMode = mode === 'edit';
  const slugChanged = isEditMode && slug !== existingSlug;
  const publishing = phase === 'publishing';
  const canPublishWithSlug = slug !== '' && (slugStatus === 'available' || slug === existingSlug);
  const displayUrl = resultUrl ? `${window.location.origin}${resultUrl}` : '';

  const slugHintMap: Partial<Record<SlugStatus, ReactNode>> = {
    invalid:  <span className="text-destructive">{t('publish.slugInvalid')}</span>,
    checking: <span className="text-muted-foreground">{t('publish.slugChecking')}</span>,
    taken:    <span className="text-destructive">{t('publish.slugTaken')}</span>,
    available:<span className="text-emerald-500">{t('publish.slugAvailable')}</span>,
  };

  // ── Handlers ───────────────────────────────────────────────────────────────

  const validateAndCheck = (value: string) => {
    clearTimeout(debounceRef.current);
    if (!value) return setSlugStatus('idle');
    if (!SLUG_RE.test(value)) return setSlugStatus('invalid');
    if (value === existingSlug) return setSlugStatus('idle');
    setSlugStatus('checking');
    debounceRef.current = setTimeout(async () => {
      try {
        const { available } = await checkSlugAvailability(projectId, value);
        setSlugStatus(available ? 'available' : 'taken');
      } catch {
        setSlugStatus('idle');
      }
    }, 500);
  };

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(val);
    validateAndCheck(val);
  };

  const handlePublish = async (useSlug: boolean) => {
    setIsPublishing(true);
    try {
      await onPublish(useSlug && slug ? slug : undefined);
    } catch {
      // error phase is driven by errorMessage prop
    } finally {
      setIsPublishing(false);
    }
  };

  const handleCopy = () => {
    if (!resultUrl) return;
    navigator.clipboard.writeText(`${window.location.origin}${resultUrl}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCancelEditing = () => {
    setSlug(existingSlug ?? '');
    setSlugStatus('idle');
    setIsEditingSlug(false);
  };

  // ── Slug input field + hint (shared between create & edit-editing) ─────────

  const renderSlugField = (showHintWhen: (s: string) => boolean) => (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground">{t('publish.slugLabel')}</label>
      <SlugInput
        value={slug}
        onChange={handleSlugChange}
        placeholder={t('publish.slugPlaceholder')}
        disabled={publishing}
      />
      <div className="h-4 text-xs">{showHintWhen(slug) ? (slugHintMap[slugStatus] ?? null) : null}</div>
    </div>
  );

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md p-6 border-border/60 bg-surface/95 backdrop-blur-xl">
        <DialogClose onClose={() => onOpenChange(false)} />

        {/* ── Input / Publishing phase ── */}
        {(phase === 'input' || publishing) && (
          <div className="flex flex-col space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full flex items-center justify-center bg-primary/10 shrink-0">
                <Globe className="w-5 h-5 text-primary" />
              </div>
              <div>
                <DialogTitle className="text-lg font-medium tracking-tight">
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
                  <SlugPreview slugValue={existingSlug!} />
                </div>

                <p className="text-xs text-amber-500/90">{t('publish.overwriteWarning')}</p>

                <div className="flex gap-2 pt-1">
                  <button
                    onClick={() => setIsEditingSlug(true)}
                    disabled={publishing}
                    className={`flex items-center gap-1.5 ${BTN_SECONDARY}`}
                  >
                    <Pencil size={13} />
                    {t('publish.changeUrl')}
                  </button>
                  <PrimaryButton disabled={publishing} onClick={() => handlePublish(true)}>
                    <PublishButtonContent publishing={publishing} label={publishing ? t('publish.publishing') : t('publish.republish')} />
                  </PrimaryButton>
                </div>
              </>
            )}

            {/* Edit mode — actively editing */}
            {isEditMode && isEditingSlug && (
              <>
                {renderSlugField((s) => !!s && s !== existingSlug)}

                {slug && slug !== existingSlug && slugStatus === 'available' && (
                  <SlugPreview slugValue={slug} />
                )}

                {slugChanged && (
                  <p className="text-xs text-amber-500/90">{t('publish.slugChangeWarning')}</p>
                )}

                <div className="flex gap-2 pt-1">
                  <button onClick={handleCancelEditing} disabled={publishing} className={BTN_SECONDARY}>
                    {t('publish.cancelChange')}
                  </button>
                  <PrimaryButton disabled={publishing || !canPublishWithSlug} onClick={() => handlePublish(true)}>
                    <PublishButtonContent
                      publishing={publishing}
                      label={publishing ? t('publish.publishing') : slugChanged ? t('publish.republishWithNewSlug') : t('publish.republish')}
                    />
                  </PrimaryButton>
                </div>
              </>
            )}

            {/* Create mode */}
            {!isEditMode && (
              <>
                {renderSlugField((s) => !!s)}

                {slug && slugStatus === 'available' && <SlugPreview slugValue={slug} />}

                <div className="flex gap-2 pt-1">
                  <button onClick={() => handlePublish(false)} disabled={publishing} className={`flex-1 ${BTN_SECONDARY}`}>
                    {t('publish.skipSlug')}
                  </button>
                  <PrimaryButton disabled={publishing || !canPublishWithSlug} onClick={() => handlePublish(true)}>
                    <PublishButtonContent publishing={publishing} label={publishing ? t('publish.publishing') : t('publish.publishWithSlug')} />
                  </PrimaryButton>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Success phase ── */}
        {phase === 'success' && (
          <div className="flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-2 bg-primary/10">
              <Check className="w-6 h-6 text-primary" />
            </div>
            <DialogTitle className="text-xl font-medium tracking-tight">
              {t('publish.successfullyPublished')}
            </DialogTitle>
            <p className="text-sm text-muted-foreground/80 pb-2">{t('publish.projectIsLive')}</p>

            <div className="flex items-center w-full gap-2 p-1.5 bg-muted/40 rounded-lg border border-border/50">
              <div className="flex-1 truncate px-3 py-1.5 text-sm font-mono text-muted-foreground bg-transparent outline-none">
                {displayUrl}
              </div>
              <button
                onClick={handleCopy}
                className="p-2 h-full rounded-md hover:bg-muted/80 text-foreground transition-colors group"
                title={t('publish.copyLink')}
              >
                {copied
                  ? <Check size={16} className="text-primary" />
                  : <Copy size={16} className="group-hover:text-primary transition-colors" />}
              </button>
            </div>

            <div className="w-full flex gap-3 pt-4">
              <button onClick={() => onOpenChange(false)} className={`flex-1 ${BTN_SECONDARY}`}>
                {t('common.close')}
              </button>
              {resultUrl && (
                <a
                  href={resultUrl}
                  target="_blank"
                  rel="noreferrer"
                  className={BTN_PRIMARY}
                  onClick={() => onOpenChange(false)}
                >
                  <ExternalLink size={16} />
                  {t('publish.openLive')}
                </a>
              )}
            </div>
          </div>
        )}

        {/* ── Error phase ── */}
        {phase === 'error' && (
          <div className="flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-12 h-12 rounded-full flex items-center justify-center mb-2 bg-destructive/10">
              <AlertCircle className="w-6 h-6 text-destructive" />
            </div>
            <DialogTitle className="text-xl font-medium tracking-tight">
              {t('publish.publishFailed')}
            </DialogTitle>
            <p className="text-sm text-muted-foreground/80 pb-2">{errorMessage}</p>
            <div className="w-full flex gap-3 pt-4">
              <button onClick={() => onOpenChange(false)} className={`flex-1 ${BTN_SECONDARY}`}>
                {t('common.close')}
              </button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
