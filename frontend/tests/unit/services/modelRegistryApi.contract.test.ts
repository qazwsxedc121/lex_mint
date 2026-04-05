import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createModel,
  createProvider,
  deleteModel,
  deleteProvider,
  getDefaultConfig,
  getModel,
  getProvider,
  getReasoningSupportedPatterns,
  listModels,
  listProviders,
  setDefaultConfig,
  testModelConnection,
  updateModel,
  updateProvider,
} from '../../../src/services/modelRegistryApi';

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

describe('modelRegistryApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected provider CRUD routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'p1' }] });
    const providers = await listProviders(true);
    expect(providers).toEqual([{ id: 'p1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/models/providers?enabled_only=true');

    getMock.mockResolvedValueOnce({ data: { id: 'p1' } });
    const provider = await getProvider('p1', true);
    expect(provider).toEqual({ id: 'p1' });
    expect(getMock).toHaveBeenCalledWith('/api/models/providers/p1?include_masked_key=true');

    await createProvider({ id: 'p1', name: 'Provider 1' } as never);
    expect(postMock).toHaveBeenCalledWith('/api/models/providers', { id: 'p1', name: 'Provider 1' });

    await updateProvider('p1', { name: 'Provider 1B' } as never);
    expect(putMock).toHaveBeenCalledWith('/api/models/providers/p1', { name: 'Provider 1B' });

    await deleteProvider('p1');
    expect(deleteMock).toHaveBeenCalledWith('/api/models/providers/p1');
  });

  it('uses expected model CRUD routes and filtered list params', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'm1' }] });
    const models = await listModels('p1', true);
    expect(models).toEqual([{ id: 'm1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/models/list?provider_id=p1&enabled_only=true');

    getMock.mockResolvedValueOnce({ data: { id: 'm1' } });
    const model = await getModel('provider:model-id');
    expect(model).toEqual({ id: 'm1' });
    expect(getMock).toHaveBeenCalledWith('/api/models/list/provider:model-id');

    await createModel({ id: 'm1', provider_id: 'p1', name: 'Model 1' } as never);
    expect(postMock).toHaveBeenCalledWith('/api/models/list', {
      id: 'm1',
      provider_id: 'p1',
      name: 'Model 1',
    });

    await updateModel('provider:model-id', { name: 'Model 1B' } as never);
    expect(putMock).toHaveBeenCalledWith('/api/models/list/provider:model-id', { name: 'Model 1B' });

    await deleteModel('provider:model-id');
    expect(deleteMock).toHaveBeenCalledWith('/api/models/list/provider:model-id');
  });

  it('uses expected default/test/reasoning routes', async () => {
    postMock.mockResolvedValueOnce({ data: { success: true, message: 'ok' } });
    const test = await testModelConnection('p1:m1');
    expect(test).toEqual({ success: true, message: 'ok' });
    expect(postMock).toHaveBeenCalledWith('/api/models/test-connection', {
      model_id: 'p1:m1',
    });

    getMock.mockResolvedValueOnce({ data: { provider_id: 'p1', model_id: 'm1' } });
    const defaults = await getDefaultConfig();
    expect(defaults).toEqual({ provider_id: 'p1', model_id: 'm1' });
    expect(getMock).toHaveBeenCalledWith('/api/models/default');

    await setDefaultConfig('p1', 'm1');
    expect(putMock).toHaveBeenCalledWith('/api/models/default?provider_id=p1&model_id=m1');

    getMock.mockResolvedValueOnce({ data: ['gpt-*'] });
    const patterns = await getReasoningSupportedPatterns();
    expect(patterns).toEqual(['gpt-*']);
    expect(getMock).toHaveBeenCalledWith('/api/models/reasoning-patterns');
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const badRequest = Object.assign(new Error('bad request'), { response: { status: 400 } });
    const notFound = Object.assign(new Error('not found'), { response: { status: 404 } });
    const conflict = Object.assign(new Error('conflict'), { response: { status: 409 } });
    const serverError = Object.assign(new Error('server error'), { response: { status: 500 } });

    getMock.mockRejectedValueOnce(badRequest);
    await expect(listProviders()).rejects.toBe(badRequest);

    postMock.mockRejectedValueOnce(notFound);
    await expect(createModel({ id: 'm1' } as never)).rejects.toBe(notFound);

    putMock.mockRejectedValueOnce(conflict);
    await expect(updateProvider('p1', { name: 'x' } as never)).rejects.toBe(conflict);

    deleteMock.mockRejectedValueOnce(serverError);
    await expect(deleteModel('p1:m1')).rejects.toBe(serverError);
  });
});
