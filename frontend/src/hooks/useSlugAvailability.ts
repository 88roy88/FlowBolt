import { useQuery } from '@tanstack/react-query';
import { checkSlugAvailability } from '../services/api';
import { SLUG_RE, usePublishStore } from '../stores/publish';
import { useDebouncedValue } from './useDebouncedValue';

export type SlugStatus = 'idle' | 'checking' | 'available' | 'taken' | 'invalid';

export function useSlugAvailability(): { status: SlugStatus; canPublish: boolean } {
  const slug = usePublishStore((s) => s.slug);
  const initialSlug = usePublishStore((s) => s.initialSlug);
  const projectId = usePublishStore((s) => s.projectId);
  const debouncedSlug = useDebouncedValue(slug, 400);

  const query = useQuery({
    queryKey: ['slug-check', projectId, debouncedSlug],
    queryFn: ({ signal }) => checkSlugAvailability(projectId!, debouncedSlug, { signal }),
    enabled:
      !!projectId &&
      !!debouncedSlug &&
      SLUG_RE.test(debouncedSlug) &&
      debouncedSlug !== initialSlug,
    // availability is time-sensitive — override global staleTime: Infinity
    staleTime: 30_000,
    gcTime: 120_000,
    retry: false,
  });

  const status = deriveSlugStatus(slug, debouncedSlug, initialSlug, query.isFetching, query.data);
  const canPublish = canPublishSlug(slug, status, initialSlug);
  return { status, canPublish };
}

export function canPublishSlug(slug: string, status: SlugStatus, initialSlug: string): boolean {
  return !!slug && (status === 'available' || slug === initialSlug);
}

export function deriveSlugStatus(
  slug: string,
  debouncedSlug: string,
  initialSlug: string,
  isFetching: boolean,
  data: { available: boolean } | undefined,
): SlugStatus {
  if (!slug || slug === initialSlug) return 'idle';
  if (!SLUG_RE.test(slug)) return 'invalid';
  if (isFetching || debouncedSlug !== slug) return 'checking';
  if (data) return data.available ? 'available' : 'taken';
  return 'idle';
}
