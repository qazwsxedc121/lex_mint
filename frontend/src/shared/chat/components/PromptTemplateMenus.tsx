import type { KeyboardEventHandler, RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import type { PromptTemplate } from '../../../types/promptTemplate';
import { normalizeTemplateTrigger, type PendingTemplateInsert } from '../hooks/usePromptTemplateComposer';
import type { SlashCommandSuggestion } from '../slashCommands';

interface PromptTemplateMenuProps {
  filteredTemplates: PromptTemplate[];
  isOpen: boolean;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onInsertTemplate: (template: PromptTemplate) => void;
  onRetry: () => void;
  onSearchChange: (value: string) => void;
  onSearchKeyDown: KeyboardEventHandler<HTMLInputElement>;
  onSetActiveIndex: (index: number) => void;
  onTogglePinned: (templateId: string) => void;
  pinnedTemplateSet: Set<string>;
  promptTemplates: PromptTemplate[];
  recentTemplateSet: Set<string>;
  searchInputRef: RefObject<HTMLInputElement | null>;
  searchValue: string;
  selectedIndex: number;
}

export function PromptTemplateMenu({
  filteredTemplates,
  isOpen,
  loading,
  error,
  onClose,
  onInsertTemplate,
  onRetry,
  onSearchChange,
  onSearchKeyDown,
  onSetActiveIndex,
  onTogglePinned,
  pinnedTemplateSet,
  promptTemplates,
  recentTemplateSet,
  searchInputRef,
  searchValue,
  selectedIndex,
}: PromptTemplateMenuProps) {
  const { t } = useTranslation('chat');

  if (!isOpen) {
    return null;
  }

  return (
    <>
      <div className="fixed inset-0 z-10" onClick={onClose} />
      <div className="absolute left-0 bottom-full mb-2 w-80 bg-white dark:bg-gray-800 rounded-md shadow-lg z-20 border border-gray-200 dark:border-gray-700" data-name="input-box-template-menu">
        <div className="p-2 border-b border-gray-200 dark:border-gray-700 space-y-2">
          <div className="text-xs text-gray-500 dark:text-gray-400">
            {t('input.promptTemplates')}
          </div>
          <input
            ref={searchInputRef}
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            onKeyDown={onSearchKeyDown}
            placeholder={t('input.searchTemplates')}
            className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="max-h-72 overflow-auto">
          {loading && (
            <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
              {t('input.loadingTemplates')}
            </div>
          )}
          {!loading && error && (
            <div className="px-3 py-2 space-y-2">
              <div className="text-sm text-red-600 dark:text-red-400">
                {error}
              </div>
              <button
                type="button"
                onClick={onRetry}
                className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
              >
                {t('common:retry')}
              </button>
            </div>
          )}
          {!loading && !error && promptTemplates.length === 0 && (
            <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
              {t('input.noTemplates')}
            </div>
          )}
          {!loading && !error && promptTemplates.length > 0 && filteredTemplates.length === 0 && (
            <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
              {t('input.noMatchingTemplates')}
            </div>
          )}
          {!loading && !error && filteredTemplates.map((template, index) => {
            const isPinned = pinnedTemplateSet.has(template.id);
            const isRecent = recentTemplateSet.has(template.id);
            const isActive = index === selectedIndex;
            const templateTrigger = normalizeTemplateTrigger(template);

            return (
              <div
                key={template.id}
                onMouseEnter={() => onSetActiveIndex(index)}
                className={`flex items-start gap-2 px-2 py-2 border-b border-gray-100 dark:border-gray-700/60 ${
                  isActive ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                }`}
                data-name="input-box-template-row"
              >
                <button
                  type="button"
                  onClick={() => onInsertTemplate(template)}
                  className="flex-1 min-w-0 text-left"
                >
                  <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {template.name}
                  </div>
                  {templateTrigger && (
                    <div className="text-[11px] text-blue-600 dark:text-blue-300 truncate">
                      /{templateTrigger}
                    </div>
                  )}
                  {template.description && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                      {template.description}
                    </div>
                  )}
                  {(isPinned || isRecent) && (
                    <div className="mt-1 flex items-center gap-1 text-[10px] uppercase tracking-wide">
                      {isPinned && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
                          {t('input.pinned')}
                        </span>
                      )}
                      {isRecent && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                          {t('input.recent')}
                        </span>
                      )}
                    </div>
                  )}
                </button>

                <button
                  type="button"
                  onClick={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    onTogglePinned(template.id);
                  }}
                  className={`px-2 py-1 text-xs rounded border ${
                    isPinned
                      ? 'border-amber-300 dark:border-amber-700 text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-900/30'
                      : 'border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                  title={isPinned ? t('input.unpinTemplate') : t('input.pinTemplate')}
                >
                  {isPinned ? t('input.pinned') : t('input.pin')}
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

interface SlashSuggestionMenuProps {
  loading: boolean;
  commandSuggestions: SlashCommandSuggestion[];
  error: string | null;
  onSelectCommand: (command: SlashCommandSuggestion) => void;
  onInsertTemplate: (template: PromptTemplate) => void;
  onRetry: () => void;
  onSetActiveIndex: (index: number) => void;
  pinnedTemplateSet: Set<string>;
  promptTemplates: PromptTemplate[];
  query: string;
  recentTemplateSet: Set<string>;
  selectedIndex: number;
  templates: PromptTemplate[];
}

export function SlashSuggestionMenu({
  loading,
  commandSuggestions,
  error,
  onSelectCommand,
  onInsertTemplate,
  onRetry,
  onSetActiveIndex,
  pinnedTemplateSet,
  promptTemplates,
  query,
  recentTemplateSet,
  selectedIndex,
  templates,
}: SlashSuggestionMenuProps) {
  const { t } = useTranslation('chat');
  const totalSuggestions = commandSuggestions.length + templates.length;

  return (
    <div className="absolute left-0 right-0 bottom-full mb-2 bg-white dark:bg-gray-800 rounded-md border border-gray-200 dark:border-gray-700 shadow-lg z-20" data-name="input-box-slash-menu">
      <div className="px-3 py-2 border-b border-gray-200 dark:border-gray-700 text-xs text-gray-500 dark:text-gray-400">
        {t('input.slashHint')}
      </div>
      <div className="max-h-60 overflow-auto">
        {loading && (
          <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
            {t('input.loadingTemplates')}
          </div>
        )}
        {!loading && error && (
          <div className="px-3 py-2 space-y-2">
            <div className="text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
            <button
              type="button"
              onClick={onRetry}
              className="text-sm text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
            >
              {t('common:retry')}
            </button>
          </div>
        )}
        {!loading && !error && promptTemplates.length === 0 && (
          <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
            {t('input.noTemplates')}
          </div>
        )}
        {!loading && !error && promptTemplates.length > 0 && totalSuggestions === 0 && (
          <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
            {t('input.noMatchingSlash', { query })}
          </div>
        )}
        {!loading && !error && commandSuggestions.map((command, index) => {
          const isActive = index === selectedIndex;
          return (
            <button
              key={command.id}
              type="button"
              onMouseEnter={() => onSetActiveIndex(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onSelectCommand(command)}
              className={`w-full text-left px-3 py-2 border-b border-gray-100 dark:border-gray-700/60 ${
                isActive
                  ? 'bg-blue-50 dark:bg-blue-900/20'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              <div className="flex items-center gap-2">
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  /{command.trigger}
                </div>
                <span className="px-1.5 py-0.5 rounded bg-violet-100 dark:bg-violet-900/40 text-[10px] uppercase tracking-wide text-violet-700 dark:text-violet-300">
                  {t('input.slashCommandType')}
                </span>
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                {command.description}
              </div>
            </button>
          );
        })}
        {!loading && !error && templates.map((template, index) => {
          const globalIndex = commandSuggestions.length + index;
          const isActive = globalIndex === selectedIndex;
          const isPinned = pinnedTemplateSet.has(template.id);
          const isRecent = recentTemplateSet.has(template.id);
          const templateTrigger = normalizeTemplateTrigger(template);

          return (
            <button
              key={template.id}
              type="button"
              onMouseEnter={() => onSetActiveIndex(globalIndex)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onInsertTemplate(template)}
              className={`w-full text-left px-3 py-2 border-b border-gray-100 dark:border-gray-700/60 ${
                isActive
                  ? 'bg-blue-50 dark:bg-blue-900/20'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                {template.name}
              </div>
              {templateTrigger && (
                <div className="text-[11px] text-blue-600 dark:text-blue-300 truncate">
                  /{templateTrigger}
                </div>
              )}
              <div className="mt-1">
                <span className="px-1.5 py-0.5 rounded bg-sky-100 dark:bg-sky-900/40 text-[10px] uppercase tracking-wide text-sky-700 dark:text-sky-300">
                  {t('input.slashTemplateType')}
                </span>
              </div>
              {template.description && (
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {template.description}
                </div>
              )}
              {(isPinned || isRecent) && (
                <div className="mt-1 flex items-center gap-1 text-[10px] uppercase tracking-wide">
                  {isPinned && (
                    <span className="px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
                      {t('input.pinned')}
                    </span>
                  )}
                  {isRecent && (
                    <span className="px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
                      {t('input.recent')}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface TemplateVariableModalProps {
  errors: Record<string, string>;
  pendingInsert: PendingTemplateInsert | null;
  onBackdropClick: (event: React.MouseEvent) => void;
  onCancel: () => void;
  onChangeValue: (variable: string, value: string) => void;
  onSubmit: () => void;
}

export function TemplateVariableModal({
  errors,
  pendingInsert,
  onBackdropClick,
  onCancel,
  onChangeValue,
  onSubmit,
}: TemplateVariableModalProps) {
  const { t } = useTranslation('chat');

  if (!pendingInsert) {
    return null;
  }

  return (
    <div
      data-name="input-box-template-variables-backdrop"
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onBackdropClick}
    >
      <div
        data-name="input-box-template-variables-modal"
        className="bg-white dark:bg-gray-800 rounded-lg p-5 w-full max-w-lg mx-4 shadow-xl"
      >
        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">
          {t('input.templateVariablesTitle')}
        </h3>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
          {t('input.templateVariablesDescription', { name: pendingInsert.template.name })}
        </p>

        <form
          data-name="input-box-template-variables-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              onCancel();
            }
          }}
        >
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            {pendingInsert.variables.map((variable, index) => (
              <div key={variable.key} data-name="input-box-template-variable-row">
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                  {variable.label}
                  {variable.required && <span className="text-red-500 ml-1">*</span>}
                </label>
                {variable.description && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">
                    {variable.description}
                  </p>
                )}
                {variable.type === 'select' ? (
                  <select
                    autoFocus={index === 0}
                    value={pendingInsert.values[variable.key] || ''}
                    onChange={(event) => onChangeValue(variable.key, event.target.value)}
                    className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">{t('common:select')}</option>
                    {variable.options.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                ) : variable.type === 'boolean' ? (
                  <select
                    autoFocus={index === 0}
                    value={pendingInsert.values[variable.key] || ''}
                    onChange={(event) => onChangeValue(variable.key, event.target.value)}
                    className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">{t('common:select')}</option>
                    <option value="true">{t('common:yes')}</option>
                    <option value="false">{t('common:no')}</option>
                  </select>
                ) : (
                  <input
                    autoFocus={index === 0}
                    type={variable.type === 'number' ? 'number' : 'text'}
                    value={pendingInsert.values[variable.key] || ''}
                    onChange={(event) => onChangeValue(variable.key, event.target.value)}
                    placeholder={t('input.templateVariablePlaceholder', { name: variable.label })}
                    className="w-full rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-sm text-gray-900 dark:text-gray-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                )}
                {errors[variable.key] && (
                  <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                    {errors[variable.key]}
                  </p>
                )}
              </div>
            ))}
          </div>

          <div className="flex justify-end gap-3 mt-5">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              {t('common:cancel')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
            >
              {t('input.insertFilledTemplate')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
