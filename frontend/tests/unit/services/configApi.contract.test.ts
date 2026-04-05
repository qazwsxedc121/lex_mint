import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  generateTitleManually,
  getSearchConfig,
  getTitleGenerationConfig,
  getWebpageConfig,
  updateSearchConfig,
  updateTitleGenerationConfig,
  updateWebpageConfig,
} from '../../../src/services/configApi';

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();

vi.mock('../../../src/services/apiClient', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    put: (...args: unknown[]) => putMock(...args),
  },
}));

describe('configApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
  });

  it('uses expected get/update routes for search, webpage, and title generation config', async () => {
    getMock.mockResolvedValueOnce({ data: { provider: 'duckduckgo' } });
    expect(await getSearchConfig()).toEqual({ provider: 'duckduckgo' });
    expect(getMock).toHaveBeenCalledWith('/api/search/config');

    await updateSearchConfig({ timeout_seconds: 3 });
    expect(putMock).toHaveBeenCalledWith('/api/search/config', { timeout_seconds: 3 });

    getMock.mockResolvedValueOnce({ data: { enabled: true } });
    expect(await getWebpageConfig()).toEqual({ enabled: true });
    expect(getMock).toHaveBeenCalledWith('/api/webpage/config');

    await updateWebpageConfig({ max_urls: 5 });
    expect(putMock).toHaveBeenCalledWith('/api/webpage/config', { max_urls: 5 });

    getMock.mockResolvedValueOnce({ data: { enabled: true } });
    expect(await getTitleGenerationConfig()).toEqual({ enabled: true });
    expect(getMock).toHaveBeenCalledWith('/api/title-generation/config');

    await updateTitleGenerationConfig({ trigger_threshold: 4 });
    expect(putMock).toHaveBeenCalledWith('/api/title-generation/config', { trigger_threshold: 4 });
  });

  it('uses expected generateTitleManually route and context params', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'ok', title: 'T1' } });
    const result = await generateTitleManually('s1', 'project', 'p1');
    expect(result).toEqual({ message: 'ok', title: 'T1' });
    expect(postMock).toHaveBeenCalledWith(
      '/api/title-generation/generate?context_type=project&project_id=p1',
      { session_id: 's1' },
    );
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const badRequest = Object.assign(new Error('bad request'), { response: { status: 400 } });
    const serverError = Object.assign(new Error('server error'), { response: { status: 500 } });

    getMock.mockRejectedValueOnce(badRequest);
    await expect(getSearchConfig()).rejects.toBe(badRequest);

    putMock.mockRejectedValueOnce(serverError);
    await expect(updateTitleGenerationConfig({ enabled: false })).rejects.toBe(serverError);
  });
});
