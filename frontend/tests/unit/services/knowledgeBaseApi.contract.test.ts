import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createKnowledgeBase,
  deleteDocument,
  deleteKnowledgeBase,
  getKnowledgeBase,
  getRagConfig,
  listDocuments,
  listKnowledgeBaseChunks,
  listKnowledgeBases,
  reprocessDocument,
  updateKnowledgeBase,
  updateRagConfig,
} from '../../../src/services/knowledgeBaseApi';

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

describe('knowledgeBaseApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected knowledge-base CRUD and document routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'kb1' }] });
    expect(await listKnowledgeBases()).toEqual([{ id: 'kb1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/knowledge-bases');

    getMock.mockResolvedValueOnce({ data: { id: 'kb1' } });
    expect(await getKnowledgeBase('kb1')).toEqual({ id: 'kb1' });
    expect(getMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1');

    postMock.mockResolvedValueOnce({ data: { id: 'kb1' } });
    expect(await createKnowledgeBase({ name: 'KB 1' } as never)).toEqual({ id: 'kb1' });
    expect(postMock).toHaveBeenCalledWith('/api/knowledge-bases', { name: 'KB 1' });

    putMock.mockResolvedValueOnce({ data: { id: 'kb1', name: 'KB 1B' } });
    expect(await updateKnowledgeBase('kb1', { name: 'KB 1B' } as never)).toEqual({ id: 'kb1', name: 'KB 1B' });
    expect(putMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1', { name: 'KB 1B' });

    await deleteKnowledgeBase('kb1');
    expect(deleteMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1');

    getMock.mockResolvedValueOnce({ data: [{ id: 'doc1' }] });
    expect(await listDocuments('kb1')).toEqual([{ id: 'doc1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1/documents');

    await deleteDocument('kb1', 'doc1');
    expect(deleteMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1/documents/doc1');

    await reprocessDocument('kb1', 'doc1');
    expect(postMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1/documents/doc1/reprocess');
  });

  it('uses expected chunks and rag config routes', async () => {
    getMock.mockResolvedValueOnce({ data: [{ id: 'c1' }] });
    expect(await listKnowledgeBaseChunks('kb1', { docId: 'doc1', limit: 5 })).toEqual([{ id: 'c1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/knowledge-bases/kb1/chunks?doc_id=doc1&limit=5');

    getMock.mockResolvedValueOnce({ data: { retrieval_top_k: 6 } });
    expect(await getRagConfig()).toEqual({ retrieval_top_k: 6 });
    expect(getMock).toHaveBeenCalledWith('/api/rag/config');

    await updateRagConfig({ retrieval_top_k: 8 } as never);
    expect(putMock).toHaveBeenCalledWith('/api/rag/config', { retrieval_top_k: 8 });
  });

  it('propagates non-2xx errors from apiClient', async () => {
    const notFound = Object.assign(new Error('not found'), { response: { status: 404 } });
    deleteMock.mockRejectedValueOnce(notFound);
    await expect(deleteKnowledgeBase('missing')).rejects.toBe(notFound);
  });
});
