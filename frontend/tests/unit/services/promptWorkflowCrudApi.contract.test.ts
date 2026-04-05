import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createPromptTemplate,
  createWorkflow,
  deletePromptTemplate,
  deleteWorkflow,
  getPromptTemplate,
  getWorkflow,
  getWorkflowRun,
  listPromptTemplates,
  listWorkflowRuns,
  listWorkflows,
  updatePromptTemplate,
  updateWorkflow,
} from '../../../src/services/promptWorkflowCrudApi';

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('../../../src/services/apiClient', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    put: (...args: unknown[]) => putMock(...args),
    delete: (...args: unknown[]) => deleteMock(...args),
  },
}));

describe('promptWorkflowCrudApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected prompt-template CRUD routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 't1' }] });
    const list = await listPromptTemplates();
    expect(list).toEqual([{ id: 't1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/prompt-templates');

    getMock.mockResolvedValueOnce({ data: { id: 't1' } });
    const one = await getPromptTemplate('t1');
    expect(one).toEqual({ id: 't1' });
    expect(getMock).toHaveBeenCalledWith('/api/prompt-templates/t1');

    await createPromptTemplate({ name: 'n1', template: 'hello {{name}}' });
    expect(postMock).toHaveBeenCalledWith('/api/prompt-templates', {
      name: 'n1',
      template: 'hello {{name}}',
    });

    await updatePromptTemplate('t1', { name: 'renamed' });
    expect(putMock).toHaveBeenCalledWith('/api/prompt-templates/t1', { name: 'renamed' });

    await deletePromptTemplate('t1');
    expect(deleteMock).toHaveBeenCalledWith('/api/prompt-templates/t1');
  });

  it('uses expected workflow CRUD and run routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'w1' }] });
    const workflows = await listWorkflows();
    expect(workflows).toEqual([{ id: 'w1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/workflows');

    getMock.mockResolvedValueOnce({ data: { id: 'w1', name: 'wf' } });
    const workflow = await getWorkflow('w1');
    expect(workflow.id).toBe('w1');
    expect(getMock).toHaveBeenCalledWith('/api/workflows/w1');

    postMock.mockResolvedValueOnce({ data: { id: 'w2' } });
    const workflowId = await createWorkflow({ name: 'wf2', nodes: [], edges: [] });
    expect(workflowId).toBe('w2');
    expect(postMock).toHaveBeenCalledWith('/api/workflows', { name: 'wf2', nodes: [], edges: [] });

    await updateWorkflow('w1', { name: 'wf1-updated' });
    expect(putMock).toHaveBeenCalledWith('/api/workflows/w1', { name: 'wf1-updated' });

    await deleteWorkflow('w1');
    expect(deleteMock).toHaveBeenCalledWith('/api/workflows/w1');

    getMock.mockResolvedValueOnce({ data: [{ id: 'r1' }] });
    const runs = await listWorkflowRuns('w1', 25);
    expect(runs).toEqual([{ id: 'r1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/workflows/w1/runs', {
      params: { limit: 25 },
    });

    getMock.mockResolvedValueOnce({ data: { id: 'r1' } });
    const run = await getWorkflowRun('w1', 'r1');
    expect(run).toEqual({ id: 'r1' });
    expect(getMock).toHaveBeenCalledWith('/api/workflows/w1/runs/r1');
  });
});
