/**
 * SessionSelector - Lightweight session selector for project chat
 * Provides dropdown menu to switch between sessions and create new ones
 */

import { Fragment } from 'react';
import { Menu, Transition } from '@headlessui/react';
import { ChevronDownIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline';
import type { Session } from '../../../types/message';

interface SessionSelectorProps {
  sessions: Session[];           // Session list
  currentSessionId: string | null; // Currently selected session
  onSelectSession: (sessionId: string) => void;  // Switch session
  onCreateSession: () => void;   // Create new session
  onDeleteSession: (sessionId: string) => void;  // Delete session
}

export default function SessionSelector({
  sessions,
  currentSessionId,
  onSelectSession,
  onCreateSession,
  onDeleteSession,
}: SessionSelectorProps) {
  const currentSession = sessions.find((s) => s.session_id === currentSessionId);
  const currentTitle = currentSession?.title || 'New Conversation';

  const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Prevent menu item click
    if (window.confirm('Delete this conversation?')) {
      onDeleteSession(sessionId);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {/* Session Dropdown */}
      <Menu as="div" className="relative flex-1">
        <Menu.Button className="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm hover:bg-gray-100 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <span className="truncate">{currentTitle}</span>
          <ChevronDownIcon className="h-4 w-4 ml-2 flex-shrink-0 text-gray-500 dark:text-gray-400" />
        </Menu.Button>

        <Transition
          as={Fragment}
          enter="transition ease-out duration-100"
          enterFrom="transform opacity-0 scale-95"
          enterTo="transform opacity-100 scale-100"
          leave="transition ease-in duration-75"
          leaveFrom="transform opacity-100 scale-100"
          leaveTo="transform opacity-0 scale-95"
        >
          <Menu.Items className="absolute left-0 right-0 mt-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-lg z-10 max-h-60 overflow-auto focus:outline-none">
            {sessions.length === 0 ? (
              <div className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">
                No conversations
              </div>
            ) : (
              sessions.map((session) => (
                <Menu.Item key={session.session_id}>
                  {({ active }) => (
                    <div
                      className={`
                        flex items-center justify-between px-3 py-2 text-sm cursor-pointer
                        ${
                          session.session_id === currentSessionId
                            ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                            : active
                            ? 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                            : 'text-gray-900 dark:text-white'
                        }
                      `}
                      onClick={() => onSelectSession(session.session_id)}
                    >
                      <span className="truncate flex-1">{session.title || 'New Conversation'}</span>
                      <button
                        onClick={(e) => handleDeleteClick(e, session.session_id)}
                        className="ml-2 p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/20 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-red-400"
                        title="Delete conversation"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </Menu.Item>
              ))
            )}
          </Menu.Items>
        </Transition>
      </Menu>

      {/* New Conversation Button */}
      <button
        onClick={onCreateSession}
        className="flex items-center gap-1 px-3 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        title="New conversation"
      >
        <PlusIcon className="h-4 w-4" />
        <span>New</span>
      </button>
    </div>
  );
}
