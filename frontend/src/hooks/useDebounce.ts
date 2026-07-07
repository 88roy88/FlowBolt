import { useEffect, useMemo, useRef, useState } from 'react';
import { debounce, type Debounced, type DebounceOptions } from '../utils/debounce';

export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  ms: number,
  opts: DebounceOptions = {}
): Debounced<A> {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const { leading, maxWait } = opts;
  const debounced = useMemo(
    () => debounce((...args: A) => fnRef.current(...args), ms, { leading, maxWait }),
    [ms, leading, maxWait]
  );

  useEffect(() => debounced.cancel, [debounced]);
  return debounced;
}

export function useDebouncedValue<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  const update = useDebouncedCallback(setDebounced, ms);
  useEffect(() => update(value), [value, update]);
  return debounced;
}
