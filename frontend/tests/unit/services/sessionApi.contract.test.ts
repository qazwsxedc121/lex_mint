import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  branchSession,
  clearAllMessages,
  copySession,
  createSession,
  deleteMessage,
  deleteSession,
  getSession,
  insertSeparator,
  listSessions,
  moveSession,
  searchSessions,
  updateGroupAssistants,
  updateMessageContent,
  updateSessionAssistant,
  updateSessionModel,
  updateSessionParamOverrides,
  updateSessionTarget,
  updateSessionTitle,
} from '../../../src/services/sessionApi';

const getMock = vi.fn();
const deleteMock = vi.fn();
const putMock = vi.fn();
const postMock = vi.fn();

vi.mock('../../../src/services/apiClient', () => ({
  api: {
    get: (...args: unknown[]) => getMock(...args),
    delete: (...args: unknown[]) => deleteMock(...args),
    put: (...args: unknown[]) => putMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
}));

describe('sessionApi contract', () => {
  beforeEach(() => {
    getMock.mockReset();
    deleteMock.mockReset();
    putMock.mockReset();
    postMock.mockReset();
  });

  it('uses POST /api/sessions for createSession', async () => {
    postMock.mockResolvedValue({ data: { session_id: 's1' } });
    const sessionId = await createSession(
      undefined,
      'assistant-1',
      'project',
      'p1',
      true,
      ['a1', 'a2'],
      'committee',
      { turns: 2 },
      'assistant',
    );
    expect(sessionId).toBe('s1');
    expect(postMock).toHaveBeenCalledWith('/api/sessions?context_type=project&project_id=p1', {
      target_type: 'assistant',
      assistant_id: 'assistant-1',
      temporary: true,
      group_assistants: ['a1', 'a2'],
      group_mode: 'committee',
      group_settings: { turns: 2 },
    });
  });

  it('uses GET /api/sessions for listSessions', async () => {
    getMock.mockResolvedValue({ data: { sessions: [{ session_id: 's1' }] } });
    const sessions = await listSessions('project', 'p1');
    expect(sessions).toEqual([{ session_id: 's1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/sessions?context_type=project&project_id=p1');
  });

  it('uses GET /api/sessions/{id} for getSession', async () => {
    getMock.mockResolvedValue({ data: { session_id: 's1', state: { messages: [] } } });
    const session = await getSession('s1', 'chat');
    expect(session.session_id).toBe('s1');
    expect(getMock).toHaveBeenCalledWith('/api/sessions/s1?context_type=chat');
  });

  it('uses DELETE /api/sessions/{id} for deleteSession', async () => {
    await deleteSession('s1', 'project', 'p1');
    expect(deleteMock).toHaveBeenCalledWith('/api/sessions/s1?context_type=project&project_id=p1');
  });

  it('uses GET /api/sessions/search for searchSessions', async () => {
    getMock.mockResolvedValue({ data: { results: [{ session_id: 's1' }] } });
    const results = await searchSessions('hello', 'chat');
    expect(results).toEqual([{ session_id: 's1' }]);
    expect(getMock).toHaveBeenCalledWith('/api/sessions/search?q=hello&context_type=chat');
  });

  it('uses PUT /api/sessions/{id}/title for updateSessionTitle', async () => {
    await updateSessionTitle('s1', 'new title', 'chat');
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/title?context_type=chat', {
      title: 'new title',
    });
  });

  it('uses POST /api/sessions/{id}/branch for branchSession', async () => {
    postMock.mockResolvedValue({ data: { session_id: 'branched' } });
    const branchedId = await branchSession('s1', 'm1', 'chat');
    expect(branchedId).toBe('branched');
    expect(postMock).toHaveBeenCalledWith('/api/sessions/s1/branch?context_type=chat', {
      message_id: 'm1',
    });
  });

  it('uses DELETE /api/chat/message for deleteMessage', async () => {
    await deleteMessage('s1', 'm1', 'project', 'p1');
    expect(deleteMock).toHaveBeenCalledWith(
      '/api/chat/message?context_type=project&project_id=p1',
      {
        data: {
          session_id: 's1',
          message_id: 'm1',
          context_type: 'project',
          project_id: 'p1',
        },
      },
    );
  });

  it('uses PUT /api/chat/message for updateMessageContent', async () => {
    await updateMessageContent('s1', 'm1', 'new content', 'chat');
    expect(putMock).toHaveBeenCalledWith('/api/chat/message?context_type=chat', {
      session_id: 's1',
      message_id: 'm1',
      content: 'new content',
      context_type: 'chat',
      project_id: undefined,
    });
  });

  it('uses POST /api/chat/separator for insertSeparator', async () => {
    postMock.mockResolvedValue({ data: { message_id: 'sep-1' } });
    const messageId = await insertSeparator('s1', 'chat');
    expect(messageId).toBe('sep-1');
    expect(postMock).toHaveBeenCalledWith('/api/chat/separator?context_type=chat', {
      session_id: 's1',
      context_type: 'chat',
      project_id: undefined,
    });
  });

  it('uses POST /api/chat/clear for clearAllMessages', async () => {
    await clearAllMessages('s1', 'project', 'p1');
    expect(postMock).toHaveBeenCalledWith('/api/chat/clear?context_type=project&project_id=p1', {
      session_id: 's1',
      context_type: 'project',
      project_id: 'p1',
    });
  });

  it('uses POST /api/sessions/{id}/move and /copy with overloaded signatures', async () => {
    postMock.mockResolvedValueOnce({ data: {} });
    await moveSession('s1', 'project', 'p1');
    expect(postMock).toHaveBeenCalledWith('/api/sessions/s1/move?context_type=chat', {
      target_context_type: 'project',
      target_project_id: 'p1',
    });

    postMock.mockResolvedValueOnce({ data: {} });
    await moveSession('s1', 'chat', undefined, 'project', 'p2');
    expect(postMock).toHaveBeenCalledWith('/api/sessions/s1/move?context_type=chat', {
      target_context_type: 'project',
      target_project_id: 'p2',
    });

    postMock.mockResolvedValueOnce({ data: { session_id: 'copied-1' } });
    const copied1 = await copySession('s1', 'project', 'p3');
    expect(copied1).toBe('copied-1');
    expect(postMock).toHaveBeenCalledWith('/api/sessions/s1/copy?context_type=chat', {
      target_context_type: 'project',
      target_project_id: 'p3',
    });

    postMock.mockResolvedValueOnce({ data: { session_id: 'copied-2' } });
    const copied2 = await copySession('s1', 'chat', undefined, 'project', 'p4');
    expect(copied2).toBe('copied-2');
    expect(postMock).toHaveBeenCalledWith('/api/sessions/s1/copy?context_type=chat', {
      target_context_type: 'project',
      target_project_id: 'p4',
    });
  });

  it('uses PUT /api/sessions/{id}/model and /assistant', async () => {
    await updateSessionModel('s1', 'provider:model', 'chat');
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/model?context_type=chat', {
      model_id: 'provider:model',
    });

    await updateSessionAssistant('s1', 'assistant-1', 'project', 'p1');
    expect(putMock).toHaveBeenCalledWith(
      '/api/sessions/s1/assistant?context_type=project&project_id=p1',
      { assistant_id: 'assistant-1' },
    );
  });

  it('uses PUT /api/sessions/{id}/target for both target overloads', async () => {
    await updateSessionTarget('s1', 'assistant', { assistantId: 'a1' });
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/target?context_type=chat', {
      target_type: 'assistant',
      assistant_id: 'a1',
      model_id: undefined,
    });

    await updateSessionTarget('s1', 'model', 'project', 'p1', { modelId: 'provider:model' });
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/target?context_type=project&project_id=p1', {
      target_type: 'model',
      assistant_id: undefined,
      model_id: 'provider:model',
    });
  });

  it('uses PUT /api/sessions/{id}/group-assistants and /param-overrides', async () => {
    await updateGroupAssistants('s1', ['a1', 'a2'], 'chat');
    expect(putMock).toHaveBeenCalledWith('/api/sessions/s1/group-assistants?context_type=chat', {
      group_assistants: ['a1', 'a2'],
    });

    await updateSessionParamOverrides('s1', { temperature: 0.2 }, 'project', 'p1');
    expect(putMock).toHaveBeenCalledWith(
      '/api/sessions/s1/param-overrides?context_type=project&project_id=p1',
      { param_overrides: { temperature: 0.2 } },
    );
  });
});
