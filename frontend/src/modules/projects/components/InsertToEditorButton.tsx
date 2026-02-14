/**
 * InsertToEditorButton - Button to insert message content into the editor
 * Only visible in Projects module when an editor is available
 */

import React, { useState } from 'react';
import { DocumentArrowDownIcon, CheckIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';
import { useProjectEditor } from '../contexts/ProjectEditorContext';

interface InsertToEditorButtonProps {
  content: string;
}

/**
 * Remove thinking blocks from content
 */
function removeThinkingBlocks(content: string): string {
  return content.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
}

export const InsertToEditorButton: React.FC<InsertToEditorButtonProps> = ({
  content,
}) => {
  const { t } = useTranslation('projects');
  const editorContext = useProjectEditor();
  const [inserted, setInserted] = useState(false);

  // Only show when editor context is available (show for both user and assistant messages)
  if (!editorContext) {
    return null;
  }

  const { insertToEditor, isEditorAvailable } = editorContext;

  const handleInsert = () => {
    if (!isEditorAvailable) return;

    // Remove thinking blocks before inserting
    const cleanedContent = removeThinkingBlocks(content);

    // Insert into editor
    insertToEditor(cleanedContent);

    // Show success feedback
    setInserted(true);
    setTimeout(() => setInserted(false), 2000);
  };

  return (
    <button
      onClick={handleInsert}
      disabled={!isEditorAvailable}
      className={`group relative p-1 rounded border transition-colors ${
        isEditorAvailable
          ? 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 border-gray-300 dark:border-gray-600'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 border-gray-300 dark:border-gray-600 cursor-not-allowed opacity-50'
      }`}
      title={inserted ? t('insertButton.inserted') : isEditorAvailable ? t('insertButton.insert') : t('insertButton.noFile')}
      data-name="insert-to-editor-button"
    >
      {inserted ? (
        <CheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
      ) : (
        <DocumentArrowDownIcon className="w-4 h-4" />
      )}
      <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        {inserted ? t('insertButton.inserted') : isEditorAvailable ? t('insertButton.insert') : t('insertButton.noFile')}
      </span>
    </button>
  );
};
