import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation } from '@tanstack/react-query';
import { useChatStore } from '../../../stores/chat';
import { enhancePrompt } from '../../../services/api';

export function useEnhancePrompt(
  projectId: string | null,
  value: string,
  setValue: (next: string) => void,
  onApplied: (text: string) => void
) {
  const { t } = useTranslation();
  const [originalDraft, setOriginalDraft] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const selectedModel = useChatStore((s) => s.selectedModel);
  const selectedDataSources = useChatStore((s) => s.selectedDataSources);
  const setError = useChatStore((s) => s.setError);

  const apply = useCallback(
    (text: string) => {
      setValue(text);
      requestAnimationFrame(() => onApplied(text));
    },
    [setValue, onApplied]
  );

  const mutation = useMutation({
    mutationFn: () => {
      const controller = new AbortController();
      abortRef.current = controller;
      return enhancePrompt(
        projectId!,
        {
          content: value.trim(),
          model: selectedModel,
          dataSourceNames: selectedDataSources.map((ds) => ds.name),
        },
        controller.signal
      );
    },
    onSuccess: (enhanced) => {
      setOriginalDraft(value);
      apply(enhanced);
    },
    onError: (err: Error) => {
      if (err.name !== 'AbortError') setError(t('chat.enhance.failed'));
    },
  });

  const undo = useCallback(() => {
    if (originalDraft === null) return;
    setOriginalDraft(null);
    apply(originalDraft);
  }, [originalDraft, apply]);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setOriginalDraft((previous) => (previous === null ? previous : null));
  }, []);

  return {
    enhance: mutation.mutate,
    isEnhancing: mutation.isPending,
    canUndo: originalDraft !== null,
    undo,
    reset,
  };
}
