import { useTranslation } from 'react-i18next';
import {
  CheckIcon,
  DocumentTextIcon,
  MinusIcon,
  PencilSquareIcon,
  PhotoIcon,
  PlusIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import type { UploadedFile } from '../../../types/message';

export interface ChatBlock {
  id: string;
  title: string;
  content: string;
  collapsed: boolean;
  isEditing: boolean;
  kind: 'context' | 'note';
  language?: string;
  source?: { filePath: string; startLine: number; endLine: number };
  isAttachmentNote?: boolean;
  attachmentFilename?: string;
  draftTitle?: string;
  draftContent?: string;
}

interface InputComposerBlocksProps {
  blocks: ChatBlock[];
  onCancelEdit: (blockId: string) => void;
  onRemove: (blockId: string) => void;
  onSaveEdit: (blockId: string) => void;
  onStartEdit: (blockId: string) => void;
  onToggleCollapsed: (blockId: string) => void;
  onUpdateDraft: (blockId: string, updates: { draftTitle?: string; draftContent?: string }) => void;
}

export function InputComposerBlocks({
  blocks,
  onCancelEdit,
  onRemove,
  onSaveEdit,
  onStartEdit,
  onToggleCollapsed,
  onUpdateDraft,
}: InputComposerBlocksProps) {
  const { t } = useTranslation('chat');

  if (blocks.length === 0) {
    return null;
  }

  return (
    <div data-name="input-box-blocks" className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 space-y-2 bg-gray-50 dark:bg-gray-900/40">
      {blocks.map((block) => {
        const draftTitle = block.draftTitle ?? block.title;
        const displayTitle = block.title || 'Block';
        const draftContent = block.draftContent ?? block.content;
        const contentLength = block.isEditing ? (draftContent?.length || 0) : block.content.length;
        const metaLabel = block.isAttachmentNote
          ? t('input.block.attachment')
          : t('input.block.chars', { count: contentLength });
        const collapseDisabled = block.isEditing;

        return (
          <div
            key={block.id}
            data-name="input-block"
            className="rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 overflow-hidden"
          >
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 dark:bg-gray-700">
              <button
                onClick={() => onToggleCollapsed(block.id)}
                disabled={collapseDisabled}
                className={`p-1 rounded ${
                  collapseDisabled
                    ? 'text-gray-400 dark:text-gray-500 cursor-not-allowed'
                    : 'hover:bg-gray-200 dark:hover:bg-gray-600'
                }`}
                title={collapseDisabled ? t('input.block.finishEditing') : block.collapsed ? t('input.block.expandBlock') : t('input.block.collapseBlock')}
              >
                {block.collapsed ? (
                  <PlusIcon className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                ) : (
                  <MinusIcon className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                )}
              </button>
              {block.isEditing ? (
                <input
                  value={draftTitle}
                  onChange={(event) => onUpdateDraft(block.id, { draftTitle: event.target.value })}
                  className="flex-1 min-w-0 text-sm font-medium px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  placeholder={t('input.block.blockTitle')}
                />
              ) : (
                <div className="flex-1 text-sm font-medium text-gray-800 dark:text-gray-100 truncate">
                  {displayTitle}
                </div>
              )}
              <span className="text-xs text-gray-500 dark:text-gray-400">{metaLabel}</span>
              {block.isEditing ? (
                <>
                  <button
                    onClick={() => onSaveEdit(block.id)}
                    className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-300"
                    title={t('input.block.saveBlock')}
                  >
                    <CheckIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => onCancelEdit(block.id)}
                    className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300"
                    title={t('input.block.cancelEdit')}
                  >
                    <XMarkIcon className="h-4 w-4" />
                  </button>
                </>
              ) : (
                <>
                  <button
                    onClick={() => onStartEdit(block.id)}
                    className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-600 dark:text-gray-300"
                    title={t('input.block.editBlock')}
                  >
                    <PencilSquareIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => onRemove(block.id)}
                    className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400"
                    title={t('input.block.removeBlock')}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>

            {!block.collapsed && (
              <div className="px-3 py-2 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
                {block.isEditing ? (
                  <div className="space-y-2">
                    {block.isAttachmentNote ? (
                      <div className="text-xs text-gray-600 dark:text-gray-300">
                        Attachment: {block.attachmentFilename || 'file'}
                      </div>
                    ) : (
                      <textarea
                        value={draftContent}
                        onChange={(event) => onUpdateDraft(block.id, { draftContent: event.target.value })}
                        className="w-full min-h-[120px] max-h-64 resize-none rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-2 overflow-auto"
                        placeholder={t('input.block.blockContent')}
                      />
                    )}
                  </div>
                ) : (
                  <div className="text-xs text-gray-700 dark:text-gray-200 whitespace-pre-wrap max-h-64 overflow-auto">
                    {block.isAttachmentNote
                      ? `Attachment: ${block.attachmentFilename || 'file'}`
                      : block.content}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface InputComposerAttachmentsProps {
  attachments: UploadedFile[];
  onRemoveAttachment: (index: number) => void;
}

export function InputComposerAttachments({
  attachments,
  onRemoveAttachment,
}: InputComposerAttachmentsProps) {
  const { t } = useTranslation('chat');

  if (attachments.length === 0) {
    return null;
  }

  return (
    <div data-name="input-box-attachments" className="px-4 py-2 border-b border-gray-200 dark:border-gray-700 space-y-1">
      {attachments.map((attachment, index) => {
        const isImage = attachment.mime_type.startsWith('image/');

        return (
          <div
            key={`${attachment.filename}-${index}`}
            className="flex items-center gap-2 px-3 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800"
          >
            {isImage ? (
              <PhotoIcon className="h-4 w-4 flex-shrink-0" />
            ) : (
              <DocumentTextIcon className="h-4 w-4 flex-shrink-0" />
            )}
            <span className="flex-1 text-sm truncate">{attachment.filename}</span>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              ({(attachment.size / 1024).toFixed(1)} KB)
            </span>
            <button
              onClick={() => onRemoveAttachment(index)}
              className="flex-shrink-0 hover:text-red-600 dark:hover:text-red-400"
              title={t('input.removeFile')}
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
