import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  addProjectWorkspaceItem,
  applyProjectChatDiff,
  createFile,
  createFolder,
  createProjectBrowseDirectory,
  deleteFile,
  deleteFolder,
  getFileTree,
  getProjectWorkspaceState,
  listProjectBrowseRoots,
  listProjectDirectories,
  readFile,
  renameProjectPath,
  searchProjectFiles,
  searchProjectText,
  writeFile,
} from '../../../src/services/projectFilesApi';

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

describe('projectFilesApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    deleteMock.mockReset();
  });

  it('uses expected tree and file CRUD routes', async () => {
    getMock.mockResolvedValueOnce({ data: { name: 'root' } });
    await getFileTree('p1');
    expect(getMock).toHaveBeenCalledWith('/api/projects/p1/tree');

    getMock.mockResolvedValueOnce({ data: { name: 'src' } });
    await getFileTree('p1', 'src/app');
    expect(getMock).toHaveBeenCalledWith('/api/projects/p1/tree?path=src%2Fapp');

    postMock.mockResolvedValueOnce({ data: { path: 'a.txt' } });
    await createFile('p1', 'a.txt', 'hello');
    expect(postMock).toHaveBeenCalledWith('/api/projects/p1/files', {
      path: 'a.txt',
      content: 'hello',
      encoding: 'utf-8',
    });

    postMock.mockResolvedValueOnce({ data: { path: 'src' } });
    await createFolder('p1', 'src');
    expect(postMock).toHaveBeenCalledWith('/api/projects/p1/directories', { path: 'src' });

    await deleteFile('p1', 'a.txt');
    expect(deleteMock).toHaveBeenCalledWith('/api/projects/p1/files', {
      params: { path: 'a.txt' },
    });

    await deleteFolder('p1', 'src', true);
    expect(deleteMock).toHaveBeenCalledWith('/api/projects/p1/directories', {
      params: { path: 'src', recursive: true },
    });

    getMock.mockResolvedValueOnce({ data: { path: 'a.txt', content: 'hello' } });
    await readFile('p1', 'src/app.py');
    expect(getMock).toHaveBeenCalledWith('/api/projects/p1/files?path=src%2Fapp.py');

    putMock.mockResolvedValueOnce({ data: { path: 'a.txt', content: 'x' } });
    await writeFile('p1', 'a.txt', 'x', 'utf-8', 'hash1');
    expect(putMock).toHaveBeenCalledWith('/api/projects/p1/files', {
      path: 'a.txt',
      content: 'x',
      encoding: 'utf-8',
      expected_hash: 'hash1',
    });
  });

  it('uses expected project-chat and rename routes', async () => {
    postMock.mockResolvedValueOnce({ data: { ok: true } });
    await applyProjectChatDiff('p1', {
      session_id: 's1',
      pending_patch_id: 'patch-1',
    });
    expect(postMock).toHaveBeenCalledWith('/api/projects/p1/chat/apply-diff', {
      session_id: 's1',
      pending_patch_id: 'patch-1',
    });

    putMock.mockResolvedValueOnce({ data: { source_path: 'a', target_path: 'b' } });
    await renameProjectPath('p1', 'a', 'b');
    expect(putMock).toHaveBeenCalledWith('/api/projects/p1/paths/rename', {
      source_path: 'a',
      target_path: 'b',
    });
  });

  it('uses expected search routes with encoded query params', async () => {
    getMock.mockResolvedValueOnce({ data: [] });
    await searchProjectFiles('p1', 'hello world', 'src/app.py');
    expect(getMock).toHaveBeenCalledWith(
      '/api/projects/p1/files/search?query=hello+world&current_file=src%2Fapp.py',
    );

    getMock.mockResolvedValueOnce({ data: { results: [] } });
    await searchProjectText('p1', 'foo', {
      caseSensitive: true,
      useRegex: true,
      includeGlob: '**/*.py',
      excludeGlob: '**/node_modules/**',
      maxResults: 80,
      contextLines: 2,
      maxCharsPerLine: 240,
    });
    expect(getMock).toHaveBeenCalledWith(
      '/api/projects/p1/text/search?query=foo&case_sensitive=true&use_regex=true&include_glob=**%2F*.py&exclude_glob=**%2Fnode_modules%2F**&max_results=80&context_lines=2&max_chars_per_line=240',
    );
  });

  it('uses expected workspace-state and browse routes', async () => {
    getMock.mockResolvedValueOnce({ data: { project_id: 'p1' } });
    await getProjectWorkspaceState('p1');
    expect(getMock).toHaveBeenCalledWith('/api/projects/p1/workspace-state');

    postMock.mockResolvedValueOnce({ data: { project_id: 'p1' } });
    await addProjectWorkspaceItem('p1', {
      type: 'file',
      id: 'f1',
      title: 'src/app.py',
    });
    expect(postMock).toHaveBeenCalledWith('/api/projects/p1/workspace-state/items', {
      type: 'file',
      id: 'f1',
      title: 'src/app.py',
    });

    getMock.mockResolvedValueOnce({ data: [] });
    await listProjectBrowseRoots();
    expect(getMock).toHaveBeenCalledWith('/api/projects/browse/roots');

    getMock.mockResolvedValueOnce({ data: [] });
    await listProjectDirectories('D:/work');
    expect(getMock).toHaveBeenCalledWith('/api/projects/browse?path=D%3A%2Fwork');

    postMock.mockResolvedValueOnce({ data: { path: 'D:/work/newdir' } });
    await createProjectBrowseDirectory('D:/work', 'newdir');
    expect(postMock).toHaveBeenCalledWith('/api/projects/browse/directories', {
      parent_path: 'D:/work',
      name: 'newdir',
    });
  });
});
