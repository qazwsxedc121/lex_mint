import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ContextUsageBar } from '../../../../../src/shared/chat/components/ContextUsageBar';

describe('ContextUsageBar', () => {
  it('renders nothing when context budget is missing', () => {
    const { container } = render(<ContextUsageBar promptTokens={128} contextInfo={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders usage summary and segment states', () => {
    render(
      <ContextUsageBar
        promptTokens={750}
        contextInfo={{
          context_budget: 1000,
          context_window: 2000,
          estimated_prompt_tokens: 700,
          segments: [
            {
              name: 'system',
              kind: 'system',
              estimated_tokens_before: 200,
              estimated_tokens_after: 200,
              included: true,
              truncated: false,
            },
            {
              name: 'history',
              kind: 'history',
              estimated_tokens_before: 800,
              estimated_tokens_after: 550,
              included: true,
              truncated: true,
            },
            {
              name: 'files',
              kind: 'attachments',
              estimated_tokens_before: 300,
              estimated_tokens_after: 0,
              included: false,
              truncated: false,
              drop_reason: 'budget',
            },
          ],
        }}
      />
    );

    expect(screen.getByText('Context: 750 / 1,000 / 2,000 (75%)')).toBeInTheDocument();
    expect(screen.getByText('system')).toBeInTheDocument();
    expect(screen.getByText('kept')).toBeInTheDocument();
    expect(screen.getByText('trimmed')).toBeInTheDocument();
    expect(screen.getByText('budget')).toBeInTheDocument();
  });
});
