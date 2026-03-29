import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import i18n from '../../../../src/i18n';
import { ProjectSearchView } from '../../../../src/modules/projects/ProjectSearchView';
import type { ProjectTextSearchMatch } from '../../../../src/services/api';

const mockNavigate = vi.fn();
const mockSearchProjectText = vi.fn();
const mockSetCurrentFile = vi.fn();
const mockAddAgentContextItems = vi.fn();
const mockBuildSearchAgentContextItem = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useOutletContext: () => ({
      projectId: 'project-1',
      currentProject: { id: 'project-1', name: 'Alpha' },
    }),
  };
});

vi.mock('../../../../src/services/api', () => ({
  searchProjectText: (...args: unknown[]) => mockSearchProjectText(...args),
}));

vi.mock('../../../../src/stores/projectWorkspaceStore', () => ({
  useProjectWorkspaceStore: () => ({
    setCurrentFile: mockSetCurrentFile,
    addAgentContextItems: mockAddAgentContextItems,
  }),
}));

vi.mock('../../../../src/modules/projects/agentContext', () => ({
  buildSearchAgentContextItem: (...args: unknown[]) => mockBuildSearchAgentContextItem(...args),
}));

describe('ProjectSearchView', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockSearchProjectText.mockReset();
    mockSetCurrentFile.mockReset();
    mockAddAgentContextItems.mockReset();
    mockBuildSearchAgentContextItem.mockReset();
    mockBuildSearchAgentContextItem.mockReturnValue({ id: 'ctx-1' });
  });

  it('shows empty state before the user types a query', () => {
    render(<ProjectSearchView />);

    expect(screen.getByText(i18n.t('projects:workspace.search.emptyState'))).toBeInTheDocument();
    expect(mockSearchProjectText).not.toHaveBeenCalled();
  });

  it('renders search results and supports opening a hit or sending it to the agent', async () => {
    const result: ProjectTextSearchMatch = {
      file_path: 'src/app.ts',
      line_number: 12,
      line_text: 'const answer = 42;',
    };
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent');
    mockSearchProjectText.mockResolvedValue({
      results: [result],
      truncated: true,
    });

    render(<ProjectSearchView />);

    fireEvent.change(screen.getByPlaceholderText(i18n.t('projects:workspace.search.placeholder')), {
      target: { value: 'answer' },
    });

    await waitFor(() => {
      expect(mockSearchProjectText).toHaveBeenCalled();
    });

    await screen.findByText('src/app.ts');
    expect(mockSearchProjectText).toHaveBeenCalledWith('project-1', 'answer', {
      maxResults: 80,
      contextLines: 1,
      maxCharsPerLine: 240,
    });
    expect(screen.getByText(i18n.t('projects:fileTree.textSearch.truncated'))).toBeInTheDocument();

    fireEvent.click(screen.getByText('src/app.ts').closest('button') as HTMLButtonElement);
    expect(mockSetCurrentFile).toHaveBeenCalledWith('project-1', 'src/app.ts');
    expect(mockNavigate).toHaveBeenCalledWith('/projects/project-1/files');

    await waitFor(() => {
      expect(
        dispatchEventSpy.mock.calls.some(([event]) =>
          event instanceof CustomEvent &&
          event.type === 'project-open-line' &&
          event.detail?.filePath === 'src/app.ts' &&
          event.detail?.line === 12
        )
      ).toBe(true);
    });

    fireEvent.click(screen.getByRole('button', { name: i18n.t('projects:workspace.agent.sendToAgent') }));
    expect(mockBuildSearchAgentContextItem).toHaveBeenCalledWith(result, 'answer');
    expect(mockAddAgentContextItems).toHaveBeenCalledWith('project-1', [{ id: 'ctx-1' }]);
    expect(mockNavigate).toHaveBeenLastCalledWith('/projects/project-1/agent');
  });

  it('shows backend error text when the search request fails', async () => {
    mockSearchProjectText.mockRejectedValue({
      response: {
        data: {
          detail: 'Search backend failed',
        },
      },
    });

    render(<ProjectSearchView />);

    fireEvent.change(screen.getByPlaceholderText(i18n.t('projects:workspace.search.placeholder')), {
      target: { value: 'broken' },
    });

    await waitFor(() => {
      expect(screen.getByText('Search backend failed')).toBeInTheDocument();
    });
  });
});
