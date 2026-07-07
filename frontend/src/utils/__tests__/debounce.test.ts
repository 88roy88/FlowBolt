import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { debounce, throttle } from '../debounce';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('debounce', () => {
  it('fires once on the trailing edge after a burst', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('a');
    debounced('b');
    debounced('c');
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('c');
  });

  it('resets the window on each call', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    vi.advanceTimersByTime(80);
    debounced();
    vi.advanceTimersByTime(80);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(20);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('flush runs the pending call immediately with the latest args', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced('x');
    debounced.flush();
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('x');

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('flush with nothing pending is a no-op', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced.flush();
    expect(fn).not.toHaveBeenCalled();
  });

  it('cancel drops the pending call', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);

    debounced();
    debounced.cancel();
    vi.advanceTimersByTime(100);
    expect(fn).not.toHaveBeenCalled();
  });

  it('does not fire when never called', () => {
    const fn = vi.fn();
    debounce(fn, 100);

    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });

  it('leading: true fires immediately on the first call with its args', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 1000, { leading: true });

    debounced('a');
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith('a');
  });

  it('a lone leading call schedules no trailing fire', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 1000, { leading: true });

    debounced('a');
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('leading + burst: exactly one trailing fire with the latest args, no re-fire within cooldown', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 1000, { leading: true });

    debounced('a');
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(100);
    debounced('b');
    vi.advanceTimersByTime(100);
    debounced('c');
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith('c');
  });

  it('maxWait forces invocation despite continuous calls', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 250, { maxWait: 1000 });

    for (let t = 0; t <= 800; t += 100) {
      debounced(t);
      vi.advanceTimersByTime(100);
    }
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith(800);
  });

  it('after a maxWait fire, a continuing stream fires again ~maxWait later', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 250, { maxWait: 1000 });

    for (let t = 0; t <= 800; t += 100) {
      debounced(t);
      vi.advanceTimersByTime(100);
    }
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);

    for (let t = 0; t <= 800; t += 100) {
      debounced(t);
      vi.advanceTimersByTime(100);
    }
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(2);
  });

  it('quiet settle fires ms after the last call and disarms the maxWait timer', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 250, { maxWait: 1000 });

    debounced('a');
    vi.advanceTimersByTime(250);
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('cancel() disarms the maxWait timer too', () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 250, { maxWait: 1000 });

    debounced('a');
    debounced.cancel();

    vi.advanceTimersByTime(1000);
    expect(fn).not.toHaveBeenCalled();
  });

  it('throttle fires leading, then exactly once per ms, then a trailing fire', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 100);

    for (let elapsed = 0; elapsed < 350; elapsed += 30) {
      throttled(elapsed);
      vi.advanceTimersByTime(30);
    }
    expect(fn.mock.calls).toEqual([[0], [90], [180], [270]]);

    vi.advanceTimersByTime(40);
    expect(fn).toHaveBeenCalledTimes(5);
    expect(fn).toHaveBeenLastCalledWith(330);
  });

  it('a call late in the cooldown fires at lastInvoke + ms, not call time + ms', () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 1000);

    throttled('a');
    vi.advanceTimersByTime(999);
    throttled('b');

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith('b');
  });
});
