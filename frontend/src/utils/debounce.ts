export interface DebounceOptions {
  leading?: boolean;
  maxWait?: number;
}

export interface Debounced<A extends unknown[]> {
  (...args: A): void;
  cancel(): void;
  flush(): void;
}

export function debounce<A extends unknown[]>(
  fn: (...args: A) => void,
  ms: number,
  { leading = false, maxWait }: DebounceOptions = {}
): Debounced<A> {
  let pendingArgs: A | undefined;
  let quietTimer: ReturnType<typeof setTimeout> | undefined;
  let maxWaitTimer: ReturnType<typeof setTimeout> | undefined;
  let lastFireTime = -Infinity;

  function fire(args: A) {
    lastFireTime = Date.now();
    pendingArgs = undefined;
    fn(...args);
  }

  function stopTimers() {
    clearTimeout(quietTimer);
    clearTimeout(maxWaitTimer);
    quietTimer = undefined;
    maxWaitTimer = undefined;
  }

  function firePending() {
    stopTimers();
    if (pendingArgs) fire(pendingArgs);
  }

  function debounced(...args: A) {
    const idle = !quietTimer && !maxWaitTimer;

    if (leading && idle && Date.now() - lastFireTime >= ms) {
      fire(args);
      return;
    }

    pendingArgs = args;
    clearTimeout(quietTimer);
    quietTimer = setTimeout(firePending, ms);

    if (maxWait !== undefined && !maxWaitTimer) {
      const sinceLastFire = Date.now() - lastFireTime;
      const wait = sinceLastFire < maxWait ? maxWait - sinceLastFire : maxWait;
      maxWaitTimer = setTimeout(firePending, wait);
    }
  }

  debounced.cancel = () => {
    stopTimers();
    pendingArgs = undefined;
  };

  debounced.flush = firePending;

  return debounced;
}

export function throttle<A extends unknown[]>(fn: (...args: A) => void, ms: number): Debounced<A> {
  return debounce(fn, ms, { leading: true, maxWait: ms });
}
