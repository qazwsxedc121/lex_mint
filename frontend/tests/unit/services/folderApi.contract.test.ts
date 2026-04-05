import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createChatFolder,
  deleteChatFolder,
  listChatFolders,
  reorderChatFolder,
  updateChatFolder,
  updateSessionFolder,
} from '../../../src/services/folderApi';

const getMock = vi.fn();
const postMock = vi.fn();
const putMock = vi.fn();
const patchMock = vi.fn();
const deleteMock = vi.fn();

vi.mock('../../../src/services/apiClient', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
    put: (...args: unknown[]) => putMock(...args),
    patch: (...args: unknown[]) => patchMock(...args),
    delete: (...args: unknown[]) => deleteMock(...args),
  },
}));

describe('folderApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected folder CRUD and reorder routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'f1' }] });
    expect(await listChatFolders()).toEqual([{ id: 'f1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/folders');

    postMock.mockResolvedValueOnce({ data: { id: 'f1', name: 'A' } });
    expect(await createChatFolder('A')).toEqual({ id: 'f1', name: 'A' });
    expect(postMock).toHaveBeenCalledWith('/api/folders', { name: 'A' });

    putMock.mockResolvedValueOnce({ data: { id: 'f1', name: 'B' } });
    expect(await updateChatFolder('f1', 'B')).toEqual({ id: 'f1', name: 'B' });
    expect(putMock).toHaveBeenCalledWith('/api/folders/f1', { name: 'B' });

    await deleteChatFolder('f1');
    expect(deleteMock).toHaveBeenCalledWith('/api/folders/f1');

    patchMock.mockResolvedValueOnce({ data: { id: 'f1', order: 3 } });
    expect(await reorderChatFolder('f1', 3)).toEqual({ id: 'f1', order: 3 });
    expect(patchMock).toHaveBeenCalledWith('/api/folders/f1/order', { order: 3 });
  });

  it('uses expected session-folder route with context query params', async () => {
    await updateSessionFolder('s1', 'f1', 'project', 'p1');
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/folder?context_type=project&project_id=p1', {
      folder_id: 'f1',
    });
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const notFound = Object.assign(new Error('not found'), { response: { status: 404 } });
    deleteMock.mockRejectedValueOnce(notFound);
    await expect(deleteChatFolder('missing')).rejects.toBe(notFound);
  });
});
