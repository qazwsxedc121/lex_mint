import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createMemory,
  deleteMemory,
  getMemorySettings,
  listMemories,
  searchMemories,
  updateMemory,
  updateMemorySettings,
} from '../../../src/services/memoryApi';

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

describe('memoryApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected settings routes', async () => {
    getMock.mockResolvedValueOnce({ data: { enabled: true } });
    expect(await getMemorySettings()).toEqual({ enabled: true });
    expect(getMock).toHaveBeenCalledWith('/api/memory/settings');

    await updateMemorySettings({ enabled: false });
    expect(putMock).toHaveBeenCalledWith('/api/memory/settings', { enabled: false });
  });

  it('uses expected CRUD and search routes', async () => {
    getMock.mockResolvedValueOnce({ data: { items: [] } });
    expect(await listMemories({ profile_id: 'p1', include_inactive: true, limit: 20 })).toEqual({ items: [] });
    expect(getMock).toHaveBeenCalledWith('/api/memory', {
      params: { profile_id: 'p1', include_inactive: true, limit: 20 },
    });

    postMock.mockResolvedValueOnce({ data: { message: 'ok', item: { id: 'm1' } } });
    expect(await createMemory({ content: 'hello' } as never)).toEqual({ id: 'm1' });
    expect(postMock).toHaveBeenCalledWith('/api/memory', { content: 'hello' });

    putMock.mockResolvedValueOnce({ data: { message: 'ok', item: { id: 'm1', content: 'x' } } });
    expect(await updateMemory('m1', { content: 'x' } as never)).toEqual({ id: 'm1', content: 'x' });
    expect(putMock).toHaveBeenCalledWith('/api/memory/m1', { content: 'x' });

    await deleteMemory('m1');
    expect(deleteMock).toHaveBeenCalledWith('/api/memory/m1');

    postMock.mockResolvedValueOnce({ data: { results: [] } });
    expect(await searchMemories({ query: 'hello' } as never)).toEqual({ results: [] });
    expect(postMock).toHaveBeenCalledWith('/api/memory/search', { query: 'hello' });
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const unprocessable = Object.assign(new Error('unprocessable'), { response: { status: 422 } });
    putMock.mockRejectedValueOnce(unprocessable);
    await expect(updateMemorySettings({ enabled: true })).rejects.toBe(unprocessable);
  });
});
