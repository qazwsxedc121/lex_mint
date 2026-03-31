import {
  ArrowPathIcon,
  ArrowUturnRightIcon,
  ChevronDownIcon,
  ClipboardDocumentCheckIcon,
  ClipboardDocumentIcon,
  LanguageIcon,
  PencilSquareIcon,
  SpeakerWaveIcon,
  StopCircleIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';
import type { RefObject } from 'react';

interface TranslateTargetOption {
  value: string;
  label: string;
}

interface MessageActionButtonProps {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
  className?: string;
  disabled?: boolean;
}

function MessageActionButton({
  children,
  label,
  onClick,
  className,
  disabled = false,
}: MessageActionButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`group relative p-1 rounded border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${className || 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-700'}`}
      title={label}
    >
      {children}
      <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
        {label}
      </span>
    </button>
  );
}

interface MessageBubbleActionsProps {
  canDelete: boolean;
  canEdit: boolean;
  canRegenerate: boolean;
  copiedLabel: string;
  copyLabel: string;
  customActions?: React.ReactNode;
  deleteLabel: string;
  editLabel: string;
  isCopied: boolean;
  isStreaming: boolean;
  isTranslating: boolean;
  isUser: boolean;
  listenLabel: string;
  loadingLabel: string;
  mainContent: string;
  onBranch?: () => void;
  onCopy: () => void;
  onDelete: () => void;
  onEdit: () => void;
  onRegenerate: () => void;
  onSelectTranslateTarget: (target: string) => void;
  onToggleTranslateMenu: () => void;
  onTranslate: () => void;
  onTtsToggle: () => void;
  selectedTranslateLabel: string;
  selectedTranslateTarget: string;
  showTranslateMenu: boolean;
  stopLabel: string;
  translateLabel: string;
  translateMenuRef: RefObject<HTMLDivElement | null>;
  translateOptions: TranslateTargetOption[];
  ttsLoading: boolean;
  ttsPlaying: boolean;
}

export function MessageBubbleActions({
  canDelete,
  canEdit,
  canRegenerate,
  copiedLabel,
  copyLabel,
  customActions,
  deleteLabel,
  editLabel,
  isCopied,
  isStreaming,
  isTranslating,
  isUser,
  listenLabel,
  loadingLabel,
  mainContent,
  onBranch,
  onCopy,
  onDelete,
  onEdit,
  onRegenerate,
  onSelectTranslateTarget,
  onToggleTranslateMenu,
  onTranslate,
  onTtsToggle,
  selectedTranslateLabel,
  selectedTranslateTarget,
  showTranslateMenu,
  stopLabel,
  translateLabel,
  translateMenuRef,
  translateOptions,
  ttsLoading,
  ttsPlaying,
}: MessageBubbleActionsProps) {
  return (
    <div data-name="message-bubble-actions" className="flex gap-1 mt-1">
      <MessageActionButton label={isCopied ? copiedLabel : copyLabel} onClick={onCopy}>
        {isCopied ? (
          <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600 dark:text-green-400" />
        ) : (
          <ClipboardDocumentIcon className="w-4 h-4" />
        )}
      </MessageActionButton>

      {!isUser && !isStreaming && mainContent.trim() && (
        <div data-name="message-bubble-translate-control" ref={translateMenuRef} className="relative">
          <div
            className={`group relative flex rounded border overflow-hidden transition-colors ${
              isTranslating
                ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/30 hover:text-teal-700 dark:hover:text-teal-300 hover:border-teal-200 dark:hover:border-teal-800'
            }`}
          >
            <button
              onClick={onTranslate}
              disabled={isTranslating}
              className="px-1.5 py-1 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
              title={`${translateLabel} (${selectedTranslateLabel})`}
            >
              <LanguageIcon className={`w-4 h-4 ${isTranslating ? 'animate-pulse' : ''}`} />
              <span className="text-[10px] font-medium leading-none">{selectedTranslateLabel}</span>
            </button>
            <button
              onClick={onToggleTranslateMenu}
              disabled={isTranslating}
              className="px-1 py-1 border-l border-gray-300/80 dark:border-gray-600/80 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Select translation target"
            >
              <ChevronDownIcon className={`w-3 h-3 transition-transform ${showTranslateMenu ? 'rotate-180' : ''}`} />
            </button>
            <span className="absolute left-1/2 -translate-x-1/2 bottom-full mb-1 px-2 py-1 text-xs text-white bg-gray-900 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              {`${translateLabel} (${selectedTranslateLabel})`}
            </span>
          </div>

          {showTranslateMenu && (
            <div className="absolute z-20 mt-1 min-w-[132px] rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg py-1">
              {translateOptions.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => onSelectTranslateTarget(option.value)}
                  className={`w-full px-3 py-1.5 text-left text-xs transition-colors ${
                    selectedTranslateTarget === option.value
                      ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300'
                      : 'text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {!isUser && !isStreaming && mainContent.trim() && (
        <MessageActionButton
          label={ttsLoading ? loadingLabel : ttsPlaying ? stopLabel : listenLabel}
          onClick={onTtsToggle}
          disabled={ttsLoading}
          className={
            ttsPlaying
              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 hover:text-blue-700 dark:hover:text-blue-300 hover:border-blue-200 dark:hover:border-blue-800'
          }
        >
          {ttsLoading ? (
            <ArrowPathIcon className="w-4 h-4 animate-spin" />
          ) : ttsPlaying ? (
            <StopCircleIcon className="w-4 h-4" />
          ) : (
            <SpeakerWaveIcon className="w-4 h-4" />
          )}
        </MessageActionButton>
      )}

      {canEdit && (
        <MessageActionButton label={editLabel} onClick={onEdit}>
          <PencilSquareIcon className="w-4 h-4" />
        </MessageActionButton>
      )}

      {canRegenerate && (
        <MessageActionButton label="Regenerate" onClick={onRegenerate}>
          <ArrowPathIcon className="w-4 h-4" />
        </MessageActionButton>
      )}

      {!isStreaming && onBranch && (
        <MessageActionButton label="Branch" onClick={onBranch}>
          <ArrowUturnRightIcon className="w-4 h-4" />
        </MessageActionButton>
      )}

      {customActions}

      {canDelete && (
        <MessageActionButton
          label={deleteLabel}
          onClick={onDelete}
          className="bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 border-gray-300 dark:border-gray-600 hover:bg-red-100 dark:hover:bg-red-900 hover:text-red-600 dark:hover:text-red-400"
        >
          <TrashIcon className="w-4 h-4" />
        </MessageActionButton>
      )}
    </div>
  );
}

interface MessageDeleteConfirmModalProps {
  isOpen: boolean;
  onBackdropClick: React.MouseEventHandler<HTMLDivElement>;
  onCancel: React.MouseEventHandler<HTMLButtonElement>;
  onConfirm: React.MouseEventHandler<HTMLButtonElement>;
}

export function MessageDeleteConfirmModal({
  isOpen,
  onBackdropClick,
  onCancel,
  onConfirm,
}: MessageDeleteConfirmModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-name="message-bubble-delete-confirm-backdrop"
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onBackdropClick}
    >
      <div data-name="message-bubble-delete-confirm-modal" className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          Delete Message
        </h3>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          Are you sure you want to delete this message? This action cannot be undone.
        </p>
        <div className="flex gap-3 justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="px-4 py-2 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
