/**
 * Shared Chat Module - Reusable chat components and services
 *
 * This module provides a complete chat interface that can be used
 * across different parts of the application (Projects, standalone chat, etc.)
 *
 * Main exports:
 * - ChatInterface: High-level component for complete chat UI
 * - ChatServiceProvider: Service provider for dependency injection
 * - useChatServices: Hook to access chat services
 * - Individual components: ChatSidebar, ChatView, etc.
 * - Hooks: useChat, useSessions, useModelCapabilities
 */

// ==================== Components ====================

/**
 * High-level component that provides complete chat interface
 * Includes sidebar, message view, and input
 */
export { ChatInterface } from './components/ChatInterface';
export type { ChatInterfaceProps } from './components/ChatInterface';

/**
 * Individual components for custom layouts
 */
export { ChatSidebar } from './components/ChatSidebar';
export { ChatView } from './components/ChatView';
export type { ChatViewProps } from './components/ChatView';
export { ChatWelcome } from './components/ChatWelcome';
export { MessageList } from './components/MessageList';
export { MessageBubble } from './components/MessageBubble';
export { InputBox } from './components/InputBox';
export { AssistantSelector } from './components/AssistantSelector';
export { CodeBlock } from './components/CodeBlock';

// ==================== Services ====================

/**
 * Service provider for dependency injection
 * Wraps chat components to provide API, navigation, and state
 */
export { ChatServiceProvider, useChatServices } from './services/ChatServiceProvider';

/**
 * Default API implementation using backend endpoints
 */
export { defaultChatAPI } from './services/defaultChatAPI';

/**
 * Service interfaces for custom implementations
 */
export type {
  ChatAPI,
  ChatNavigation,
  ChatContextData,
  ChatServiceContextValue,
} from './services/interfaces';

// ==================== Hooks ====================

/**
 * Hook for managing chat messages and operations
 */
export { useChat } from './hooks/useChat';

/**
 * Hook for managing sessions
 */
export { useSessions } from './hooks/useSessions';

/**
 * Hook for checking model capabilities (vision, reasoning, etc.)
 */
export { useModelCapabilities } from './hooks/useModelCapabilities';

// ==================== Usage Examples ====================

/**
 * Example 1: Simple usage with defaults
 * ```tsx
 * import { ChatInterface } from '@/shared/chat';
 *
 * function MyChat() {
 *   return <ChatInterface />;
 * }
 * ```
 *
 * Example 2: Custom API for project-specific chat
 * ```tsx
 * import { ChatInterface, defaultChatAPI } from '@/shared/chat';
 * import type { ChatAPI, ChatNavigation } from '@/shared/chat';
 *
 * function ProjectChat({ projectId }: { projectId: string }) {
 *   const projectAPI: ChatAPI = {
 *     ...defaultChatAPI,
 *     createSession: async (modelId, assistantId) => {
 *       const sessionId = await defaultChatAPI.createSession(modelId, assistantId);
 *       await linkSessionToProject(sessionId, projectId);
 *       return sessionId;
 *     },
 *   };
 *
 *   const navigation: ChatNavigation = {
 *     navigateToSession: (id) => navigate(`/projects/${projectId}/chat/${id}`),
 *     navigateToRoot: () => navigate(`/projects/${projectId}`),
 *     getCurrentSessionId: () => sessionIdFromParams,
 *   };
 *
 *   return <ChatInterface api={projectAPI} navigation={navigation} />;
 * }
 * ```
 *
 * Example 3: Using with React Router nested routes
 * ```tsx
 * import { ChatInterface } from '@/shared/chat';
 *
 * function ChatModule() {
 *   const navigation = {
 *     navigateToSession: (id) => navigate(`/chat/${id}`),
 *     navigateToRoot: () => navigate('/chat'),
 *     getCurrentSessionId: () => params.sessionId,
 *   };
 *
 *   return (
 *     <ChatInterface
 *       navigation={navigation}
 *       useOutlet={true}
 *     />
 *   );
 * }
 * ```
 */
