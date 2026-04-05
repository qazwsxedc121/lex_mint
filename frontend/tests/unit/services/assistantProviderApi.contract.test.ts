import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createAssistant,
  deleteAssistant,
  fetchProviderModels,
  getAssistant,
  getBuiltinProvider,
  getDefaultAssistant,
  getDefaultAssistantId,
  getModelCapabilities,
  listAssistants,
  listBuiltinProviders,
  listProtocols,
  listProviderEndpointProfiles,
  probeProviderEndpoints,
  setDefaultAssistant,
  testProviderConnection,
  testProviderStoredConnection,
  updateAssistant,
} from '../../../src/services/assistantProviderApi';

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

describe('assistantProviderApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected assistant CRUD and default routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'a1' }] });
    const assistants = await listAssistants(true);
    expect(assistants).toEqual([{ id: 'a1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/assistants?enabled_only=true');

    getMock.mockResolvedValueOnce({ data: { id: 'a1' } });
    const assistant = await getAssistant('a1');
    expect(assistant).toEqual({ id: 'a1' });
    expect(getMock).toHaveBeenCalledWith('/api/assistants/a1');

    await createAssistant({ id: 'a1', name: 'Assistant 1' } as never);
    expect(postMock).toHaveBeenCalledWith('/api/assistants', { id: 'a1', name: 'Assistant 1' });

    await updateAssistant('a1', { name: 'Assistant 1B' } as never);
    expect(putMock).toHaveBeenCalledWith('/api/assistants/a1', { name: 'Assistant 1B' });

    await deleteAssistant('a1');
    expect(deleteMock).toHaveBeenCalledWith('/api/assistants/a1');

    getMock.mockResolvedValueOnce({ data: { default_assistant_id: 'a1' } });
    const defaultId = await getDefaultAssistantId();
    expect(defaultId).toBe('a1');
    expect(getMock).toHaveBeenCalledWith('/api/assistants/default/id');

    getMock.mockResolvedValueOnce({ data: { id: 'a1' } });
    const defaultAssistant = await getDefaultAssistant();
    expect(defaultAssistant).toEqual({ id: 'a1' });
    expect(getMock).toHaveBeenCalledWith('/api/assistants/default/assistant');

    await setDefaultAssistant('a1');
    expect(putMock).toHaveBeenCalledWith('/api/assistants/default/a1');
  });

  it('uses expected provider test/probe/profile routes', async () => {
    postMock.mockResolvedValueOnce({ data: { success: true, message: 'ok' } });
    const test1 = await testProviderConnection('openai', 'https://api.openai.com/v1', 'sk-x', 'gpt-4.1');
    expect(test1).toEqual({ success: true, message: 'ok' });
    expect(postMock).toHaveBeenCalledWith('/api/models/providers/test', {
      base_url: 'https://api.openai.com/v1',
      api_key: 'sk-x',
      provider_id: 'openai',
      model_id: 'gpt-4.1',
    });

    postMock.mockResolvedValueOnce({ data: { success: true, message: 'ok' } });
    const test2 = await testProviderStoredConnection('openai', 'https://api.openai.com/v1');
    expect(test2).toEqual({ success: true, message: 'ok' });
    expect(postMock).toHaveBeenCalledWith('/api/models/providers/test-stored', {
      provider_id: 'openai',
      base_url: 'https://api.openai.com/v1',
      model_id: undefined,
    });

    postMock.mockResolvedValueOnce({ data: { provider_id: 'openai', results: [] } });
    const probe = await probeProviderEndpoints('openai', {
      mode: 'auto',
      strict: true,
    } as never);
    expect(probe).toEqual({ provider_id: 'openai', results: [] });
    expect(postMock).toHaveBeenCalledWith('/api/models/providers/openai/probe-endpoints', {
      mode: 'auto',
      strict: true,
    });

    getMock.mockResolvedValueOnce({ data: { provider_id: 'openai', endpoint_profiles: [] } });
    const profiles = await listProviderEndpointProfiles('openai', 'cn');
    expect(profiles).toEqual({ provider_id: 'openai', endpoint_profiles: [] });
    expect(getMock).toHaveBeenCalledWith(
      '/api/models/providers/openai/endpoint-profiles?client_region_hint=cn',
    );
  });

  it('uses expected builtins/models/capabilities/protocol routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'openai' }] });
    const builtins = await listBuiltinProviders();
    expect(builtins).toEqual([{ id: 'openai' }]);
    expect(getMock).toHaveBeenCalledWith('/api/models/providers/builtin');

    getMock.mockResolvedValueOnce({ data: { id: 'openai' } });
    const builtin = await getBuiltinProvider('openai');
    expect(builtin).toEqual({ id: 'openai' });
    expect(getMock).toHaveBeenCalledWith('/api/models/providers/builtin/openai');

    postMock.mockResolvedValueOnce({ data: [{ id: 'gpt-4.1' }] });
    const models = await fetchProviderModels('openai');
    expect(models).toEqual([{ id: 'gpt-4.1' }]);
    expect(postMock).toHaveBeenCalledWith('/api/models/providers/openai/fetch-models');

    getMock.mockResolvedValueOnce({ data: { model_id: 'openai:gpt-4.1' } });
    const caps = await getModelCapabilities('openai:gpt-4.1');
    expect(caps).toEqual({ model_id: 'openai:gpt-4.1' });
    expect(getMock).toHaveBeenCalledWith('/api/models/capabilities/openai:gpt-4.1');

    getMock.mockResolvedValueOnce({ data: [{ id: 'openai' }] });
    const protocols = await listProtocols();
    expect(protocols).toEqual([{ id: 'openai' }]);
    expect(getMock).toHaveBeenCalledWith('/api/models/protocols');
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const unauthorized = Object.assign(new Error('unauthorized'), { response: { status: 401 } });
    const forbidden = Object.assign(new Error('forbidden'), { response: { status: 403 } });
    const unprocessable = Object.assign(new Error('unprocessable'), { response: { status: 422 } });
    const serverError = Object.assign(new Error('server error'), { response: { status: 500 } });

    getMock.mockRejectedValueOnce(unauthorized);
    await expect(listAssistants()).rejects.toBe(unauthorized);

    postMock.mockRejectedValueOnce(forbidden);
    await expect(testProviderConnection('x', 'https://example.com', 'sk-x')).rejects.toBe(forbidden);

    putMock.mockRejectedValueOnce(unprocessable);
    await expect(setDefaultAssistant('a1')).rejects.toBe(unprocessable);

    deleteMock.mockRejectedValueOnce(serverError);
    await expect(deleteAssistant('a1')).rejects.toBe(serverError);
  });
});
