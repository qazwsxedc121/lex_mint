import React from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { json } from '@codemirror/lang-json';
import { useTranslation } from 'react-i18next';

interface WorkflowEditorProps {
  value: string;
  parseError: string | null;
  saving: boolean;
  readOnly?: boolean;
  title?: string;
  showSaveButton?: boolean;
  onChange: (value: string) => void;
  onSave: () => void;
}

export const WorkflowEditor: React.FC<WorkflowEditorProps> = ({
  value,
  parseError,
  saving,
  readOnly = false,
  title,
  showSaveButton = true,
  onChange,
  onSave,
}) => {
  const { t } = useTranslation('workflow');

  return (
    <section
      className="rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4 space-y-3"
      data-name="workflow-editor-panel"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
          {title || t('editor.title')}
        </h3>
        {showSaveButton ? (
          <button
            type="button"
            data-name="workflow-editor-save"
            onClick={onSave}
            disabled={saving || !!parseError || readOnly}
            className="rounded-md px-3 py-1.5 text-xs font-medium bg-blue-600 text-white hover:bg-blue-500 disabled:opacity-60"
          >
            {saving ? t('actions.saving') : t('actions.save')}
          </button>
        ) : null}
      </div>

      <div className="rounded-md border border-gray-200 dark:border-gray-700 overflow-hidden">
        <CodeMirror
          value={value}
          height="380px"
          extensions={[json()]}
          onChange={readOnly ? () => undefined : onChange}
          editable={!readOnly}
          readOnly={readOnly}
          basicSetup={{
            lineNumbers: true,
            highlightActiveLine: true,
            autocompletion: true,
            bracketMatching: true,
            foldGutter: true,
          }}
        />
      </div>

      {parseError && (
        <div
          className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-700 dark:bg-red-900/30 dark:text-red-300"
          data-name="workflow-editor-parse-error"
        >
          {parseError}
        </div>
      )}
    </section>
  );
};
