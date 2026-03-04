import React from 'react';
import { useTranslation } from 'react-i18next';
import { WorkflowVisualCanvas } from './WorkflowVisualCanvas';
import { buildGraphFromDsl } from '../visual/buildGraphFromDsl';
import type { VisualGraphIssue, VisualGraphParseError } from '../visual/types';

export interface WorkflowVisualPanelProps {
  dslText: string;
  className?: string;
}

const getParseErrorReasonKey = (parseError: VisualGraphParseError): string => {
  if (parseError.code === 'invalidJson') {
    return 'visual.parseErrorReason.invalidJson';
  }
  if (parseError.code === 'invalidRoot') {
    return 'visual.parseErrorReason.invalidRoot';
  }
  if (parseError.code === 'missingNodes') {
    return 'visual.parseErrorReason.missingNodes';
  }
  if (parseError.code === 'missingEntryNodeId') {
    return 'visual.parseErrorReason.missingEntryNodeId';
  }
  return 'visual.parseErrorReason.noValidNodes';
};

const getIssueMessage = (issue: VisualGraphIssue, t: (key: string, options?: Record<string, unknown>) => string): string => {
  if (issue.code === 'duplicateNodeId') {
    return t('visual.issue.duplicateNodeId', { nodeId: issue.nodeId || '-' });
  }
  if (issue.code === 'missingTargetNode') {
    if (issue.label) {
      return t('visual.issue.missingTargetNodeWithLabel', {
        sourceId: issue.sourceId || '-',
        targetId: issue.targetId || '-',
        label: issue.label,
      });
    }
    return t('visual.issue.missingTargetNode', {
      sourceId: issue.sourceId || '-',
      targetId: issue.targetId || '-',
    });
  }
  if (issue.code === 'orphanNode') {
    return t('visual.issue.orphanNode', { nodeId: issue.nodeId || '-' });
  }
  if (issue.code === 'unknownNodeType') {
    return t('visual.issue.unknownNodeType', {
      nodeId: issue.nodeId || '-',
      nodeType: issue.nodeType || '-',
    });
  }
  if (issue.code === 'missingEntryNode') {
    return t('visual.issue.missingEntryNode', {
      entryNodeId: issue.targetId || '-',
    });
  }
  return t('visual.issue.invalidNodeShape', {
    index: typeof issue.index === 'number' ? issue.index + 1 : 0,
  });
};

export const WorkflowVisualPanel: React.FC<WorkflowVisualPanelProps> = ({ dslText, className }) => {
  const { t } = useTranslation('workflow');
  const graph = React.useMemo(() => buildGraphFromDsl(dslText), [dslText]);

  return (
    <section
      data-name="workflow-visual-panel"
      className={`rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3 ${className || ''}`}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{t('visual.title')}</h3>
        <span className="rounded border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-blue-700 dark:border-blue-700 dark:bg-blue-900/30 dark:text-blue-200">
          {t('visual.beta')}
        </span>
      </div>

      {graph.parseError ? (
        <div
          data-name="workflow-visual-parse-error"
          className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300"
        >
          {t('visual.parseError', {
            reason: t(getParseErrorReasonKey(graph.parseError)),
          })}
        </div>
      ) : graph.nodes.length === 0 ? (
        <div className="rounded-md border border-gray-300 bg-gray-50 px-3 py-8 text-center text-xs text-gray-600 dark:border-gray-600 dark:bg-gray-900/40 dark:text-gray-300">
          {t('visual.empty')}
        </div>
      ) : (
        <WorkflowVisualCanvas nodes={graph.nodes} edges={graph.edges} />
      )}

      {graph.issues.length > 0 && (
        <div data-name="workflow-visual-issues" className="space-y-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-2 dark:border-gray-700 dark:bg-gray-900/40">
          <div className="text-xs font-medium text-gray-700 dark:text-gray-200">{t('visual.issuesTitle')}</div>
          <ul className="space-y-1">
            {graph.issues.map((issue, index) => (
              <li
                key={`${issue.code}-${issue.nodeId || issue.targetId || index}`}
                className="text-xs text-gray-700 dark:text-gray-300"
              >
                <span
                  className={`mr-2 rounded px-1.5 py-0.5 text-[10px] font-medium ${
                    issue.level === 'error'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                  }`}
                >
                  {issue.level === 'error' ? t('visual.issue.levelError') : t('visual.issue.levelWarn')}
                </span>
                {getIssueMessage(issue, t)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
};
