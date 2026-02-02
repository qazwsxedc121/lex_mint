/**
 * ChatComposerContext - Provides a bridge to control the chat input from outside
 * (e.g., inserting editor content into the chat composer).
 */

import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';

export interface ChatComposerBlockInput {
  title: string;
  content?: string;
  language?: string;
  collapsed?: boolean;
  kind?: 'context' | 'note';
  source?: { filePath: string; startLine: number; endLine: number };
  isAttachmentNote?: boolean;
  attachmentFilename?: string;
}

export interface ChatComposerActions {
  insertText: (text: string) => void;
  appendText: (text: string) => void;
  focus: () => void;
  attachTextFile: (options: { filename: string; content: string; mimeType?: string }) => Promise<void>;
  addBlock: (block: ChatComposerBlockInput) => void;
}

export interface ChatComposerContextValue {
  registerComposer: (actions: ChatComposerActions | null) => void;
  insertText: (text: string) => Promise<void>;
  appendText: (text: string) => Promise<void>;
  focus: () => Promise<void>;
  attachTextFile: (options: { filename: string; content: string; mimeType?: string }) => Promise<void>;
  addBlock: (block: ChatComposerBlockInput) => Promise<void>;
  isReady: boolean;
}

type PendingAction = (actions: ChatComposerActions) => Promise<void> | void;

const ChatComposerContext = createContext<ChatComposerContextValue | null>(null);

export const useChatComposer = () => {
  const context = useContext(ChatComposerContext);
  if (!context) {
    throw new Error('useChatComposer must be used within ChatComposerProvider');
  }
  return context;
};

export const ChatComposerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const actionsRef = useRef<ChatComposerActions | null>(null);
  const pendingRef = useRef<PendingAction[]>([]);
  const [isReady, setIsReady] = useState(false);

  const registerComposer = useCallback((actions: ChatComposerActions | null) => {
    actionsRef.current = actions;
    setIsReady(!!actions);

    if (!actions) {
      return;
    }

    const pending = pendingRef.current.splice(0);
    pending.forEach((action) => {
      Promise.resolve(action(actions)).catch((err) => {
        console.error('Failed pending chat composer action', err);
      });
    });
  }, []);

  const runOrQueue = useCallback((action: PendingAction) => {
    const actions = actionsRef.current;
    if (actions) {
      return Promise.resolve(action(actions));
    }

    return new Promise<void>((resolve, reject) => {
      pendingRef.current.push(async (actionsToRun) => {
        try {
          await action(actionsToRun);
          resolve();
        } catch (err) {
          reject(err);
        }
      });
    });
  }, []);

  const insertText = useCallback((text: string) => {
    return runOrQueue((actions) => actions.insertText(text));
  }, [runOrQueue]);

  const appendText = useCallback((text: string) => {
    return runOrQueue((actions) => actions.appendText(text));
  }, [runOrQueue]);

  const focus = useCallback(() => {
    return runOrQueue((actions) => actions.focus());
  }, [runOrQueue]);

  const attachTextFile = useCallback((options: { filename: string; content: string; mimeType?: string }) => {
    return runOrQueue((actions) => actions.attachTextFile(options));
  }, [runOrQueue]);

  const addBlock = useCallback((block: ChatComposerBlockInput) => {
    return runOrQueue((actions) => actions.addBlock(block));
  }, [runOrQueue]);

  const value = useMemo<ChatComposerContextValue>(() => ({
    registerComposer,
    insertText,
    appendText,
    focus,
    attachTextFile,
    addBlock,
    isReady,
  }), [registerComposer, insertText, appendText, focus, attachTextFile, addBlock, isReady]);

  return (
    <ChatComposerContext.Provider value={value}>
      {children}
    </ChatComposerContext.Provider>
  );
};
