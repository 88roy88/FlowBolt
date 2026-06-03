import { useMutation, type UseMutationResult } from '@tanstack/react-query';
import { publishToS3 } from '../services/api';
import { usePublishStore } from '../stores/publish';
import { useSessionStore } from '../stores/session';

type PublishResult = { url: string; handle: string; published_at: string };

export function usePublishMutation(
  projectId: string | null,
): UseMutationResult<PublishResult, Error, { useSlug: boolean }> {
  return useMutation<PublishResult, Error, { useSlug: boolean }>({
    mutationFn: ({ useSlug }) => {
      const slug = usePublishStore.getState().slug;
      return publishToS3(projectId!, useSlug ? slug : undefined);
    },
    onSuccess(data) {
      if (!projectId) return;
      useSessionStore.getState().setProjectPublishedUrl(projectId, data.handle, data.published_at);
    },
  });
}
