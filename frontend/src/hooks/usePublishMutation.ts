import { useRef } from 'react';
import { useMutation, type UseMutationResult } from '@tanstack/react-query';
import { publishToS3 } from '../services/api';
import { usePublishStore } from '../stores/publish';
import { useSessionStore } from '../stores/session';
import { logger } from '../services/logger';
import type { PublishDetails } from '../types';

type PublishResult = { url: string; handle: string };
export type PublishVariables = { useSlug: boolean; details: PublishDetails };

export function usePublishMutation(
  projectId: string | null,
): UseMutationResult<PublishResult, Error, PublishVariables> {
  const startedAtRef = useRef<number | null>(null);

  return useMutation<PublishResult, Error, PublishVariables>({
    mutationFn: ({ useSlug, details }) => {
      const slug = usePublishStore.getState().slug;
      startedAtRef.current = performance.now();
      logger.info('publish_started');
      return publishToS3(projectId!, details, useSlug ? slug : undefined);
    },
    onSuccess(data, { details }) {
      if (!projectId) return;
      useSessionStore.getState().setProjectPublished(projectId, data.handle, details);
      logger.info('publish_succeeded', {
        duration_ms: startedAtRef.current ? Math.round(performance.now() - startedAtRef.current) : undefined,
        published_url: data.url,
      });
    },
    onError(error) {
      logger.error('publish_failed', {
        error_message: error.message,
        duration_ms: startedAtRef.current ? Math.round(performance.now() - startedAtRef.current) : undefined,
      });
    },
  });
}
