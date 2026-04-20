/**
 * A utility to manage an asynchronous action that should be debounced
 * and cancelled if a new one is scheduled before the timeout finishes.
 * Automatically handles AbortController signals for networking tasks.
 */
export class DebouncedAction {
  private timer: ReturnType<typeof setTimeout> | null = null;
  private controller: AbortController | null = null;

  /**
   * Cancels any pending timeout and aborts any active fetch request
   */
  cancel() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.controller) {
      this.controller.abort();
      this.controller = null;
    }
  }

  /**
   * Schedules a task to run after the specified delay.
   * If a task is already scheduled, it is cancelled.
   * 
   * @param ms Delay in milliseconds
   * @param task Function to run, receives an AbortSignal
   */
  schedule(ms: number, task: (signal: AbortSignal) => Promise<void>) {
    this.cancel();
    
    this.controller = new AbortController();
    const signal = this.controller.signal;
    
    this.timer = setTimeout(async () => {
      this.timer = null;
      try {
        await task(signal);
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') return;
        console.error('[DebouncedAction] task failed:', err);
      } finally {
        if (this.controller?.signal === signal) {
          this.controller = null;
        }
      }
    }, ms);
  }
}
