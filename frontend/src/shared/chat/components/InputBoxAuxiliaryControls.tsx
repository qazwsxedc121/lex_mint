import type { MouseEventHandler, RefObject } from 'react';
import { ChevronDownIcon, LanguageIcon } from '@heroicons/react/24/outline';

interface TranslationTargetOption {
  value: string;
  label: string;
}

interface TranslateInputControlProps {
  disabled: boolean;
  inputValue: string;
  isOpen: boolean;
  isStreaming: boolean;
  isTranslating: boolean;
  menuRef: RefObject<HTMLDivElement | null>;
  menuTitle: string;
  onSelectTarget: (target: string) => void;
  onToggleMenu: () => void;
  onTranslate: () => void;
  options: TranslationTargetOption[];
  selectedTarget: string;
  selectedTargetLabel: string;
  translateTitle: string;
  translatingTitle: string;
}

export function TranslateInputControl({
  disabled,
  inputValue,
  isOpen,
  isStreaming,
  isTranslating,
  menuRef,
  menuTitle,
  onSelectTarget,
  onToggleMenu,
  onTranslate,
  options,
  selectedTarget,
  selectedTargetLabel,
  translateTitle,
  translatingTitle,
}: TranslateInputControlProps) {
  return (
    <div data-name="input-box-translate-control" ref={menuRef} className="relative">
      <div
        className={`group relative flex rounded-md border transition-colors ${
          isTranslating
            ? 'bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 border-teal-200 dark:border-teal-800'
            : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-teal-50 dark:hover:bg-teal-900/30 hover:text-teal-700 dark:hover:text-teal-300 hover:border-teal-200 dark:hover:border-teal-800'
        }`}
      >
        <button
          type="button"
          onClick={onTranslate}
          disabled={disabled || isStreaming || isTranslating || !inputValue.trim()}
          data-name="input-box-translate-toggle"
          className="flex items-center gap-1 px-2 py-1.5 rounded-l-md disabled:opacity-50 disabled:cursor-not-allowed"
          title={`${isTranslating ? translatingTitle : translateTitle} (${selectedTargetLabel})`}
        >
          <LanguageIcon className={`h-4 w-4 ${isTranslating ? 'animate-pulse' : ''}`} />
          <span className="text-[10px] font-medium leading-none">{selectedTargetLabel}</span>
        </button>
        <button
          type="button"
          onClick={onToggleMenu}
          disabled={disabled || isStreaming || isTranslating}
          className="px-1.5 py-1.5 border-l border-gray-300/80 dark:border-gray-600/80 rounded-r-md disabled:opacity-50 disabled:cursor-not-allowed"
          title={menuTitle}
        >
          <ChevronDownIcon className={`h-3.5 w-3.5 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {isOpen && (
        <div data-name="input-box-translate-menu" className="absolute z-20 mt-1 min-w-[132px] rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-lg py-1">
          {options.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => onSelectTarget(option.value)}
              className={`w-full px-3 py-1.5 text-left text-xs transition-colors ${
                selectedTarget === option.value
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
  );
}

interface ClearMessagesConfirmModalProps {
  isOpen: boolean;
  onBackdropClick: MouseEventHandler<HTMLDivElement>;
  onCancel: () => void;
  onConfirm: () => void;
  cancelLabel: string;
  confirmLabel: string;
  message: string;
  title: string;
}

export function ClearMessagesConfirmModal({
  isOpen,
  onBackdropClick,
  onCancel,
  onConfirm,
  cancelLabel,
  confirmLabel,
  message,
  title,
}: ClearMessagesConfirmModalProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <div
      data-name="input-box-clear-confirm-backdrop"
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onBackdropClick}
    >
      <div data-name="input-box-clear-confirm-modal" className="bg-white dark:bg-gray-800 rounded-lg p-6 max-w-sm mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-2">
          {title}
        </h3>
        <p className="text-gray-600 dark:text-gray-400 mb-4">
          {message}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 transition-colors"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
