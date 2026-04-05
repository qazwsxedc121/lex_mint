import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  createProject,
  deleteProject,
  getProject,
  getToolCatalog,
  listProjects,
  updateProject,
} from '../../../src/services/projectApi';

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

describe('projectApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses GET /api/projects for listProjects', async () => {
    getMock.mockResolvedValue({ data: [{ id: 'p1' }] });
    const projects = await listProjects();
    expect(projects).toEqual([{ id: 'p1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/projects');
  });

  it('uses GET /api/tools/catalog for getToolCatalog', async () => {
    getMock.mockResolvedValue({ data: { categories: [] } });
    const catalog = await getToolCatalog();
    expect(catalog).toEqual({ categories: [] });
    expect(getMock).toHaveBeenCalledWith('/api/tools/catalog');
  });

  it('uses POST /api/projects for createProject', async () => {
    const payload = { name: 'Demo', root_path: '/tmp/demo' };
    postMock.mockResolvedValue({ data: { id: 'p1', ...payload } });
    const created = await createProject(payload);
    expect(created.id).toBe('p1');
    expect(postMock).toHaveBeenCalledWith('/api/projects', payload);
  });

  it('uses GET /api/projects/{id} for getProject', async () => {
    getMock.mockResolvedValue({ data: { id: 'p1', name: 'Demo' } });
    const project = await getProject('p1');
    expect(project).toEqual({ id: 'p1', name: 'Demo' });
    expect(getMock).toHaveBeenCalledWith('/api/projects/p1');
  });

  it('uses PUT /api/projects/{id} for updateProject', async () => {
    const payload = { name: 'Renamed' };
    putMock.mockResolvedValue({ data: { id: 'p1', name: 'Renamed' } });
    const updated = await updateProject('p1', payload);
    expect(updated.name).toBe('Renamed');
    expect(putMock).toHaveBeenCalledWith('/api/projects/p1', payload);
  });

  it('uses DELETE /api/projects/{id} for deleteProject', async () => {
    await deleteProject('p1');
    expect(deleteMock).toHaveBeenCalledWith('/api/projects/p1');
  });
});
