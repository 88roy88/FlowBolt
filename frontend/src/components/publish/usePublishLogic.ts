import { useState, useRef, useCallback } from 'react';
import { checkSlugAvailability } from '../../services/api';

export type SlugStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

const SLUG_RE = /^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$/;

interface UsePublishLogicProps {
  projectId: string;
  initialSlug: string;
  onPublish: (slug: string | undefined) => Promise<void>;
}

export function usePublishLogic({ projectId, initialSlug, onPublish }: UsePublishLogicProps) {
  const [isPublishing, setIsPublishing] = useState(false);
  const [slug, setSlug] = useState(initialSlug);
  const [slugStatus, setSlugStatus] = useState<SlugStatus>('idle');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const validateAndCheck = useCallback((value: string) => {
    clearTimeout(debounceRef.current);
    if (!value) return setSlugStatus('idle');
    if (!SLUG_RE.test(value)) return setSlugStatus('invalid');
    if (value === initialSlug) return setSlugStatus('idle');

    setSlugStatus('checking');
    debounceRef.current = setTimeout(async () => {
      try {
        const { available } = await checkSlugAvailability(projectId, value);
        setSlugStatus(available ? 'available' : 'taken');
      } catch {
        setSlugStatus('idle');
      }
    }, 500);
  }, [projectId, initialSlug]);

  const handleSlugChange = useCallback((val: string) => {
    const formatted = val.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(formatted);
    validateAndCheck(formatted);
  }, [validateAndCheck]);

  const handlePublish = async (useSlug: boolean) => {
    setIsPublishing(true);
    try {
      await onPublish(useSlug && slug ? slug : undefined);
    } finally {
      setIsPublishing(false);
    }
  };

  const resetSlug = useCallback(() => {
    setSlug(initialSlug);
    setSlugStatus('idle');
  }, [initialSlug]);

  return {
    slug,
    slugStatus,
    isPublishing,
    handleSlugChange,
    handlePublish,
    resetSlug,
    canPublish: slug !== '' && (slugStatus === 'available' || slug === initialSlug),
    isChanged: slug !== initialSlug,
  };
}
