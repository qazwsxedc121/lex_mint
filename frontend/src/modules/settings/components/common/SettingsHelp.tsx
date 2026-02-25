import React, { useState } from 'react';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/outline';
import { Modal } from './Modal';
import type { SettingsHelpConfig } from '../../config/types';

interface SettingsHelpProps {
  help: SettingsHelpConfig;
  triggerDataName?: string;
  contentDataName?: string;
}

export const SettingsHelp: React.FC<SettingsHelpProps> = ({
  help,
  triggerDataName = 'settings-help-trigger',
  contentDataName = 'settings-help-content',
}) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center justify-center rounded-full text-gray-400 transition-colors hover:text-blue-600 dark:text-gray-500 dark:hover:text-blue-300"
        title={help.openTitle}
        data-name={triggerDataName}
      >
        <QuestionMarkCircleIcon className="h-4 w-4" />
      </button>

      <Modal
        isOpen={open}
        onClose={() => setOpen(false)}
        title={help.title}
        size={help.size || 'xl'}
      >
        <div
          className="max-h-[70vh] space-y-4 overflow-y-auto pr-1 text-sm text-gray-700 dark:text-gray-300"
          data-name={contentDataName}
        >
          {help.sections.map((section, index) => (
            <section key={`${section.title}-${index}`} className="space-y-2">
              <h4 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                {section.title}
              </h4>
              {section.body && <p>{section.body}</p>}
              {section.items && section.items.length > 0 && (
                <ul className="list-disc space-y-1 pl-5">
                  {section.items.map((item, itemIndex) => (
                    <li key={`${section.title}-item-${itemIndex}`}>{item}</li>
                  ))}
                </ul>
              )}
              {section.code && (
                <pre className="overflow-x-auto rounded-md bg-gray-100 p-3 text-xs dark:bg-gray-900/60">
                  {section.code}
                </pre>
              )}
            </section>
          ))}
        </div>
      </Modal>
    </>
  );
};
