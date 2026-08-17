import { useEffect } from 'react';
import type { Dispatch, RefObject, SetStateAction } from 'react';

export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  setOpen: Dispatch<SetStateAction<boolean>>,
  open: boolean,
) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [ref, setOpen, open]);
}
