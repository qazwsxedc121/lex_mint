import { useTranslation } from 'react-i18next';
import { DocumentIcon } from '@heroicons/react/24/outline';
import type { FileSearchResult } from '../../../services/api';

interface FilePickerPopoverProps {
  isOpen: boolean;
  projectId: string;
  query: string;
  results: FileSearchResult[];
  selectedIndex: number;
  loading: boolean;
  onSelect: (filePath: string) => void;
  onClose: () => void;
}

export function FilePickerPopover({
  isOpen,
  results,
  selectedIndex,
  loading,
  onSelect,
}: FilePickerPopoverProps) {
  const { t } = useTranslation('chat');

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="absolute bottom-full mb-2 left-0 right-0 z-50"
      data-name="file-picker-popover"
    >
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Loading state */}
        {loading && (
          <div className="p-4 text-sm text-gray-500 dark:text-gray-400 text-center">
            {t('fileReference.searching')}
          </div>
        )}

        {/* No results */}
        {!loading && results.length === 0 && (
          <div className="p-4 text-sm text-gray-500 dark:text-gray-400 text-center">
            {t('fileReference.noResults')}
          </div>
        )}

        {/* Results list */}
        {!loading && results.length > 0 && (
          <div className="max-h-80 overflow-y-auto">
            {results.map((result, index) => (
              <div
                key={result.path}
                className={`
                  px-4 py-2.5 cursor-pointer border-b border-gray-100 dark:border-gray-700 last:border-b-0
                  hover:bg-gray-50 dark:hover:bg-gray-700
                  ${
                    selectedIndex === index
                      ? 'bg-blue-50 dark:bg-blue-900/20 border-l-2 border-l-blue-500'
                      : ''
                  }
                `}
                onClick={() => onSelect(result.path)}
              >
                <div className="flex items-start gap-3">
                  <DocumentIcon className="w-5 h-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 dark:text-white truncate">
                        {result.name}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 flex-shrink-0">
                        {t(`fileReference.proximityLabel.${result.proximityReason}`)}
                      </span>
                    </div>
                    {result.directory && (
                      <div className="text-xs text-gray-500 dark:text-gray-400 truncate mt-0.5">
                        {result.directory}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer hint */}
        <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700">
          <div className="text-xs text-gray-500 dark:text-gray-400 flex items-center justify-center gap-4">
            <span>↑↓ Navigate</span>
            <span>•</span>
            <span>Enter Select</span>
            <span>•</span>
            <span>Esc Close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
