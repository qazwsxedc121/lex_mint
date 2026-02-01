/**
 * ChatInterface - High-level chat component that combines sidebar and view
 *
 * This component provides a complete chat interface with:
 * - Session management (sidebar)
 * - Message display and input (view)
 * - Built-in service provider
 *
 * Usage:
 * ```tsx
 * // Simple usage with defaults
 * <ChatInterface />
 *
 * // Custom API and navigation
 * <ChatInterface
 *   api={customAPI}
 *   navigation={customNavigation}
 * />
 * ```
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { ChatSidebar } from './ChatSidebar';
import { ChatView } from './ChatView';
import { ChatServiceProvider } from '../services/ChatServiceProvider';
import { defaultChatAPI } from '../services/defaultChatAPI';
import type { ChatAPI, ChatNavigation, ChatContextData } from '../services/interfaces';

export interface ChatInterfaceProps {
  /**
   * API implementation for chat operations
   * Defaults to defaultChatAPI
   */
  api?: ChatAPI;

  /**
   * Navigation implementation for routing
   * If not provided, uses URL parameters
   */
  navigation?: ChatNavigation;

  /**
   * Legacy context data for backward compatibility
   */
  context?: ChatContextData;

  /**
   * Whether to use Outlet for rendering chat view
   * Set to true when using with React Router nested routes
   * Defaults to false (renders ChatView directly)
   */
  useOutlet?: boolean;

  /**
   * Custom content to render in outlet
   * Only used when useOutlet is true
   */
  outletContext?: any;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  api = defaultChatAPI,
  navigation,
  context,
  useOutlet = false,
  outletContext = {},
}) => {
  return (
    <ChatServiceProvider
      api={api}
      navigation={navigation}
      context={context}
    >
      <div data-name="chat-interface" className="flex flex-1">
        {/* Chat Sidebar */}
        <ChatSidebar />

        {/* Chat Content */}
        {useOutlet ? (
          <Outlet context={outletContext} />
        ) : (
          <ChatView />
        )}
      </div>
    </ChatServiceProvider>
  );
};
