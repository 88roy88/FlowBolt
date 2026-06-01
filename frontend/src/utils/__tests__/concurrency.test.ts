import { describe, it, expect, vi, beforeEach } from 'vitest';
import { DebouncedAction } from '../concurrency';

describe('DebouncedAction', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('should delay task execution', async () => {
    const checker = new DebouncedAction();
    const task = vi.fn().mockResolvedValue(undefined);

    checker.schedule(500, task);
    expect(task).not.toHaveBeenCalled();

    vi.advanceTimersByTime(499);
    expect(task).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(task).toHaveBeenCalled();
  });

  it('should cancel previous task if new one is scheduled', async () => {
    const checker = new DebouncedAction();
    const task1 = vi.fn().mockResolvedValue(undefined);
    const task2 = vi.fn().mockResolvedValue(undefined);

    checker.schedule(500, task1);
    vi.advanceTimersByTime(250);
    
    checker.schedule(500, task2);
    vi.advanceTimersByTime(250); // total 500 since task1, but task2 just started
    
    expect(task1).not.toHaveBeenCalled();
    expect(task2).not.toHaveBeenCalled();

    vi.advanceTimersByTime(250);
    expect(task1).not.toHaveBeenCalled();
    expect(task2).toHaveBeenCalled();
  });

  it('should provide a valid AbortSignal and abort it on cancellation', async () => {
    const checker = new DebouncedAction();
    let capturedSignal: AbortSignal | null = null;
    
    const task = vi.fn().mockImplementation(async (signal) => {
      capturedSignal = signal;
    });

    checker.schedule(500, task);
    vi.advanceTimersByTime(500);

    expect(task).toHaveBeenCalled();
    expect(capturedSignal).not.toBeNull();
    expect((capturedSignal as unknown as AbortSignal).aborted).toBe(false);

    checker.cancel();
    expect((capturedSignal as unknown as AbortSignal).aborted).toBe(true);
  });

  it('should update isPending state correctly', async () => {
    const checker = new DebouncedAction();
    const task = vi.fn().mockImplementation(() => new Promise(res => setTimeout(res, 100)));

    expect(checker.isPending()).toBe(false);

    checker.schedule(500, task);
    expect(checker.isPending()).toBe(true);

    vi.advanceTimersByTime(500);
    // Task is now running (timer is null, but controller is active)
    expect(checker.isPending()).toBe(true);

    // Complete the internal task timeout
    vi.advanceTimersByTime(100);
    
    // Wait for the promise to resolve
    await vi.runAllTimersAsync();
    
    expect(checker.isPending()).toBe(false);
  });

  it('should swallow AbortError but log other errors', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const checker = new DebouncedAction();
    
    const abortTask = vi.fn().mockImplementation(async () => {
      throw new DOMException('Aborted', 'AbortError');
    });

    checker.schedule(500, abortTask);
    vi.advanceTimersByTime(500);
    await vi.runAllTimersAsync();

    expect(consoleSpy).not.toHaveBeenCalled();

    const errorTask = vi.fn().mockRejectedValue(new Error('KABOOM'));
    checker.schedule(500, errorTask);
    vi.advanceTimersByTime(500);
    await vi.runAllTimersAsync();

    expect(consoleSpy).toHaveBeenCalledWith('[DebouncedAction] task failed:', expect.any(Error));
    
    consoleSpy.mockRestore();
  });
});
