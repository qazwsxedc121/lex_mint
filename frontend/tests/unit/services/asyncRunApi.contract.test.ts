import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cancelAsyncRun,
  createAsyncRun,
  createWorkflowRun,
  getAsyncRun,
  listAsyncRuns,
  resumeAsyncRun,
} from '../../../src/services/asyncRunApi';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('../../../src/services/apiClient', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
}));

describe('asyncRunApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
  });

  it('uses expected run create/list/get routes', async () => {
    postMock.mockResolvedValueOnce({ data: { run_id: 'r1' } });
    expect(await createAsyncRun({ kind: 'chat', session_id: 's1' })).toEqual({ run_id: 'r1' });
    expect(postMock).toHaveBeenCalledWith('/api/runs', { kind: 'chat', session_id: 's1' });

    postMock.mockResolvedValueOnce({ data: { run_id: 'r2' } });
    expect(
      await createWorkflowRun('wf1', { topic: 'x' }, { contextType: 'project', projectId: 'p1', streamMode: 'editor_rewrite' }),
    ).toEqual({ run_id: 'r2' });
    expect(postMock).toHaveBeenCalledWith('/api/runs', {
      kind: 'workflow',
      workflow_id: 'wf1',
      inputs: { topic: 'x' },
      session_id: undefined,
      context_type: 'project',
      project_id: 'p1',
      stream_mode: 'editor_rewrite',
      artifact_target_path: undefined,
      write_mode: undefined,
    });

    getMock.mockResolvedValueOnce({ data: { runs: [{ run_id: 'r1' }] } });
    expect(await listAsyncRuns({ limit: 10, status: 'running', contextType: 'project', projectId: 'p1' })).toEqual([
      { run_id: 'r1' },
    ]);
    expect(getMock).toHaveBeenCalledWith('/api/runs', {
      params: {
        limit: 10,
        kind: undefined,
        status: 'running',
        context_type: 'project',
        project_id: 'p1',
        session_id: undefined,
        workflow_id: undefined,
      },
    });

    getMock.mockResolvedValueOnce({ data: { run_id: 'r1', status: 'running' } });
    expect(await getAsyncRun('r1')).toEqual({ run_id: 'r1', status: 'running' });
    expect(getMock).toHaveBeenCalledWith('/api/runs/r1');
  });

  it('uses expected cancel/resume routes', async () => {
    postMock.mockResolvedValueOnce({ data: { run_id: 'r1', status: 'cancelled' } });
    expect(await cancelAsyncRun('r1')).toEqual({ run_id: 'r1', status: 'cancelled' });
    expect(postMock).toHaveBeenCalledWith('/api/runs/r1/cancel');

    postMock.mockResolvedValueOnce({ data: { run_id: 'r1', status: 'running' } });
    expect(await resumeAsyncRun('r1')).toEqual({ run_id: 'r1', status: 'running' });
    expect(postMock).toHaveBeenCalledWith('/api/runs/r1/resume', {});

    postMock.mockResolvedValueOnce({ data: { run_id: 'r1', status: 'running' } });
    expect(await resumeAsyncRun('r1', 'cp-1')).toEqual({ run_id: 'r1', status: 'running' });
    expect(postMock).toHaveBeenCalledWith('/api/runs/r1/resume', { checkpoint_id: 'cp-1' });
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const serverError = Object.assign(new Error('server error'), { response: { status: 500 } });
    getMock.mockRejectedValueOnce(serverError);
    await expect(getAsyncRun('missing')).rejects.toBe(serverError);
  });
});
