import { describe, it, expect, beforeEach } from 'vitest';
import { useErrorStore } from '../errors';

describe('preview error suppression', () => {
  beforeEach(() => {
    useErrorStore.setState({ errors: [], previewErrorsSuppressed: false });
  });

  it('clears existing app errors when preview is entered', () => {
    useErrorStore.getState().pushError({ source: 'runtime', message: 'undefined is not a function' });
    expect(useErrorStore.getState().errors).toHaveLength(1);

    useErrorStore.getState().suppressPreviewErrors(true);

    expect(useErrorStore.getState().errors).toEqual([]);
  });

  it('keeps errors when suppression is re-asserted while already previewing', () => {
    useErrorStore.getState().suppressPreviewErrors(true);
    useErrorStore.getState().pushError({ source: 'connection', message: 'Version operation failed' });

    useErrorStore.getState().suppressPreviewErrors(true);

    expect(useErrorStore.getState().errors).toHaveLength(1);
    expect(useErrorStore.getState().errors[0].message).toEqual('Version operation failed');
  });

  it('keeps errors when suppression lifts', () => {
    useErrorStore.getState().suppressPreviewErrors(true);
    useErrorStore.getState().pushError({ source: 'connection', message: 'Backend unreachable' });

    useErrorStore.getState().suppressPreviewErrors(false);

    expect(useErrorStore.getState().previewErrorsSuppressed).toBe(false);
    expect(useErrorStore.getState().errors).toHaveLength(1);
  });

  it('still drops app errors pushed while previewing', () => {
    useErrorStore.getState().suppressPreviewErrors(true);

    useErrorStore.getState().pushError({ source: 'runtime', message: 'error in the old version' });

    expect(useErrorStore.getState().errors).toEqual([]);
  });
});
