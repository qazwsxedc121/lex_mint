import { useCallback, useState } from 'react';

import type { ChatComposerBlockInput } from '../contexts/ChatComposerContext';
import type { ChatBlock } from '../components/InputComposerPanels';

const createBlockId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `block-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const normalizeBlock = (
  inputBlock: ChatComposerBlockInput,
  options?: { isEditing?: boolean },
): ChatBlock => {
  const title = inputBlock.title?.trim() || 'Block';
  const isEditing = options?.isEditing ?? false;
  return {
    id: createBlockId(),
    title,
    content: inputBlock.content ?? '',
    collapsed: inputBlock.collapsed ?? !isEditing,
    isEditing,
    kind: inputBlock.kind ?? 'note',
    language: inputBlock.language,
    source: inputBlock.source,
    isAttachmentNote: inputBlock.isAttachmentNote,
    attachmentFilename: inputBlock.attachmentFilename,
    draftTitle: isEditing ? title : undefined,
    draftContent: isEditing ? (inputBlock.content ?? '') : undefined,
  };
};

export const useInputComposerBlocks = () => {
  const [blocks, setBlocks] = useState<ChatBlock[]>([]);

  const addBlock = useCallback((inputBlock: ChatComposerBlockInput) => {
    setBlocks((prev) => [...prev, normalizeBlock(inputBlock)]);
  }, []);

  const createBlock = useCallback(() => {
    const newBlock = normalizeBlock(
      {
        title: 'New block',
        content: '',
        collapsed: false,
        kind: 'note',
      },
      { isEditing: true },
    );
    setBlocks((prev) => [...prev, newBlock]);
  }, []);

  const toggleBlockCollapsed = useCallback((blockId: string) => {
    setBlocks((prev) => prev.map((block) => (
      block.id === blockId ? { ...block, collapsed: !block.collapsed } : block
    )));
  }, []);

  const startEditBlock = useCallback((blockId: string) => {
    setBlocks((prev) => prev.map((block) => (
      block.id === blockId
        ? {
            ...block,
            isEditing: true,
            collapsed: false,
            draftTitle: block.title,
            draftContent: block.content,
          }
        : block
    )));
  }, []);

  const updateBlockDraft = useCallback((
    blockId: string,
    updates: { draftTitle?: string; draftContent?: string },
  ) => {
    setBlocks((prev) => prev.map((block) => (
      block.id === blockId ? { ...block, ...updates } : block
    )));
  }, []);

  const saveBlockEdit = useCallback((blockId: string) => {
    setBlocks((prev) => prev.map((block) => (
      block.id === blockId
        ? {
            ...block,
            title: block.draftTitle?.trim() || block.title,
            content: block.draftContent ?? block.content,
            isEditing: false,
            collapsed: true,
            draftTitle: undefined,
            draftContent: undefined,
          }
        : block
    )));
  }, []);

  const cancelBlockEdit = useCallback((blockId: string) => {
    setBlocks((prev) => prev.map((block) => (
      block.id === blockId
        ? {
            ...block,
            isEditing: false,
            draftTitle: undefined,
            draftContent: undefined,
          }
        : block
    )));
  }, []);

  const removeBlock = useCallback((blockId: string) => {
    setBlocks((prev) => prev.filter((block) => block.id !== blockId));
  }, []);

  const clearBlocks = useCallback(() => {
    setBlocks([]);
  }, []);

  const buildBlocksMessage = useCallback(() => {
    const parts: string[] = [];

    blocks.forEach((block) => {
      const contentSource = block.isEditing ? (block.draftContent ?? block.content) : block.content;
      const content = contentSource.trim();
      const title = block.isEditing ? (block.draftTitle ?? block.title) : block.title;
      if (!content && !block.isAttachmentNote) {
        return;
      }

      if (block.isAttachmentNote) {
        const header = block.source
          ? `[Context: ${block.source.filePath} lines ${block.source.startLine}-${block.source.endLine}]`
          : `[Block: ${title}]`;
        const filename = block.attachmentFilename ? ` ${block.attachmentFilename}` : ' file';
        parts.push(`${header}\n(Attached as${filename})`);
        return;
      }

      const header = block.source
        ? `[Context: ${block.source.filePath} lines ${block.source.startLine}-${block.source.endLine}]`
        : `[Block: ${title}]`;
      const fence = block.language ? `\`\`\`${block.language}` : '```';
      parts.push(`${header}\n${fence}\n${content}\n\`\`\``);
    });

    return parts.join('\n\n');
  }, [blocks]);

  return {
    addBlock,
    blocks,
    buildBlocksMessage,
    cancelBlockEdit,
    clearBlocks,
    createBlock,
    removeBlock,
    saveBlockEdit,
    startEditBlock,
    toggleBlockCollapsed,
    updateBlockDraft,
  };
};
