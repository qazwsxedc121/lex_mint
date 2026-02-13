/**
 * ChatToggleButton - Toggle button for showing/hiding chat sidebar
 */

import React from 'react';
import { ChatBubbleLeftIcon } from '@heroicons/react/24/outline';
import { useTranslation } from 'react-i18next';

interface ChatToggleButtonProps {
  isOpen: boolean;
  onToggle: () => void;
}

export const ChatToggleButton: React.FC<ChatToggleButtonProps> = ({
  isOpen,
  onToggle
}) => {
  const { t } = useTranslation('projects');

  return (
    <button
      title={isOpen ? t('chatToggle.hide') : t('chatToggle.show')}
      onClick={onToggle}
      className={`p-1.5 rounded ${
        isOpen
          ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300'
          : 'hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300'
      }`}
    >
      <ChatBubbleLeftIcon className="h-4 w-4" />
    </button>
  );
};
