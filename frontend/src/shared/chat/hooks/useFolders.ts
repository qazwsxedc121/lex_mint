/**
 * useFolders - Chat folder management hook
 */

import { useState, useEffect } from 'react';
import type { Folder } from '../../../types/folder';
import {
  listChatFolders,
  createChatFolder,
  updateChatFolder,
  deleteChatFolder,
  reorderChatFolder,
  updateSessionFolder as apiUpdateSessionFolder,
} from '../../../services/api';

const COLLAPSED_FOLDERS_KEY = 'chat-collapsed-folders';

export function useFolders() {
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem(COLLAPSED_FOLDERS_KEY);
      return new Set(saved ? JSON.parse(saved) : []);
    } catch {
      return new Set();
    }
  });

  // Load folders on mount
  useEffect(() => {
    loadFolders();
  }, []);

  // Persist collapsed state to localStorage
  useEffect(() => {
    localStorage.setItem(COLLAPSED_FOLDERS_KEY, JSON.stringify(Array.from(collapsedFolders)));
  }, [collapsedFolders]);

  const loadFolders = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await listChatFolders();
      setFolders(data);
    } catch (err) {
      console.error('Failed to load folders:', err);
      setError(err instanceof Error ? err.message : 'Failed to load folders');
    } finally {
      setLoading(false);
    }
  };

  const createFolder = async (name: string): Promise<Folder | null> => {
    try {
      setError(null);
      const newFolder = await createChatFolder(name);
      setFolders((prev) => [...prev, newFolder]);
      return newFolder;
    } catch (err) {
      console.error('Failed to create folder:', err);
      setError(err instanceof Error ? err.message : 'Failed to create folder');
      return null;
    }
  };

  const updateFolder = async (folderId: string, name: string): Promise<boolean> => {
    try {
      setError(null);
      const updated = await updateChatFolder(folderId, name);
      setFolders((prev) =>
        prev.map((f) => (f.id === folderId ? updated : f))
      );
      return true;
    } catch (err) {
      console.error('Failed to update folder:', err);
      setError(err instanceof Error ? err.message : 'Failed to update folder');
      return false;
    }
  };

  const deleteFolder = async (folderId: string): Promise<boolean> => {
    try {
      setError(null);
      await deleteChatFolder(folderId);
      setFolders((prev) => prev.filter((f) => f.id !== folderId));
      // Remove from collapsed set if present
      setCollapsedFolders((prev) => {
        const next = new Set(prev);
        next.delete(folderId);
        return next;
      });
      return true;
    } catch (err) {
      console.error('Failed to delete folder:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete folder');
      return false;
    }
  };

  const moveSessionToFolder = async (
    sessionId: string,
    folderId: string | null,
    contextType: string = 'chat',
    projectId?: string
  ): Promise<boolean> => {
    try {
      setError(null);
      await apiUpdateSessionFolder(sessionId, folderId, contextType, projectId);
      return true;
    } catch (err) {
      console.error('Failed to move session to folder:', err);
      setError(err instanceof Error ? err.message : 'Failed to move session');
      return false;
    }
  };

  const reorderFolder = async (folderId: string, newOrder: number): Promise<boolean> => {
    try {
      setError(null);
      await reorderChatFolder(folderId, newOrder);
      await loadFolders(); // Refresh to get all updated orders
      return true;
    } catch (err) {
      console.error('Failed to reorder folder:', err);
      setError(err instanceof Error ? err.message : 'Failed to reorder folder');
      return false;
    }
  };

  const toggleFolder = (folderId: string) => {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  return {
    folders,
    loading,
    error,
    collapsedFolders,
    loadFolders,
    createFolder,
    updateFolder,
    deleteFolder,
    moveSessionToFolder,
    reorderFolder,
    toggleFolder,
  };
}
