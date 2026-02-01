/**
 * ChatModule - Main entry point for the chat module
 *
 * Version 3.0: Uses shared/chat components
 * All core functionality moved to shared/chat for reusability
 */

import React from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { ChatInterface } from '../../shared/chat';
import type { ChatNavigation } from '../../shared/chat';

// Context type for child routes (backward compatibility)
interface ChatContextType {
  onAssistantRefresh?: () => void;
}

export const ChatModule: React.FC = () => {
  const navigate = useNavigate();
  const { sessionId } = useParams<{ sessionId: string }>();

  // Create navigation implementation for current module
  const navigation: ChatNavigation = {
    navigateToSession: (id) => navigate(`/chat/${id}`),
    navigateToRoot: () => navigate('/chat'),
    getCurrentSessionId: () => sessionId || null,
  };

  // Backward compatibility context for ChatView
  const outletContext: ChatContextType = {};

  return (
    <ChatInterface
      navigation={navigation}
      useOutlet={true}
      outletContext={outletContext}
    />
  );
};

// Hook for child components to access chat context (backward compatibility)
export function useChatContext() {
  return useOutletContext<ChatContextType>();
}
