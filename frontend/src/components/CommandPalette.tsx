import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  MagnifyingGlassIcon,
  PlusIcon,
  ChatBubbleLeftIcon,
  Cog6ToothIcon,
  FolderIcon,
} from '@heroicons/react/24/outline';
import { createSession, searchSessions } from '../services/api';
import type { SearchResult } from '../services/api';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

interface CommandItem {
  id: string;
  type: 'command';
  label: string;
  icon: React.ReactNode;
  action: () => void;
}

interface SessionItem {
  id: string;
  type: 'session';
  sessionId: string;
  title: string;
  matchType: 'title' | 'content';
  matchContext: string;
}

type PaletteItem = CommandItem | SessionItem;

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [sessionResults, setSessionResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Commands (static)
  const commands: CommandItem[] = useMemo(() => [
    {
      id: 'cmd-new-chat',
      type: 'command' as const,
      label: 'New Chat',
      icon: <PlusIcon className="h-4 w-4" />,
      action: async () => {
        try {
          const sessionId = await createSession(undefined, undefined, 'chat');
          navigate(`/chat/${sessionId}`);
        } catch (err) {
          console.error('Failed to create session:', err);
        }
      },
    },
    {
      id: 'cmd-temp-chat',
      type: 'command' as const,
      label: 'New Temp Chat',
      icon: <PlusIcon className="h-4 w-4" />,
      action: async () => {
        try {
          const sessionId = await createSession(undefined, undefined, 'chat', undefined, true);
          navigate(`/chat/${sessionId}`);
        } catch (err) {
          console.error('Failed to create temp session:', err);
        }
      },
    },
    {
      id: 'cmd-settings',
      type: 'command' as const,
      label: 'Settings',
      icon: <Cog6ToothIcon className="h-4 w-4" />,
      action: () => navigate('/settings'),
    },
    {
      id: 'cmd-projects',
      type: 'command' as const,
      label: 'Projects',
      icon: <FolderIcon className="h-4 w-4" />,
      action: () => navigate('/projects'),
    },
  ], [navigate]);

  // Filter commands by query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((cmd) => cmd.label.toLowerCase().includes(q));
  }, [commands, query]);

  // Build session items
  const sessionItems: SessionItem[] = useMemo(() => {
    return sessionResults.map((r) => ({
      id: `session-${r.session_id}`,
      type: 'session' as const,
      sessionId: r.session_id,
      title: r.title,
      matchType: r.match_type,
      matchContext: r.match_context,
    }));
  }, [sessionResults]);

  // Merged flat list for keyboard navigation
  const allItems: PaletteItem[] = useMemo(() => {
    return [...filteredCommands, ...sessionItems];
  }, [filteredCommands, sessionItems]);

  // Debounced session search
  useEffect(() => {
    if (!isOpen) return;

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    const trimmed = query.trim();
    if (!trimmed) {
      setSessionResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchSessions(trimmed);
        setSessionResults(results);
      } catch (err) {
        console.error('Search failed:', err);
        setSessionResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, isOpen]);

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSessionResults([]);
      setSelectedIndex(0);
      setLoading(false);
      // Focus input after render
      requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
    }
  }, [isOpen]);

  // Clamp selectedIndex when items change
  useEffect(() => {
    if (selectedIndex >= allItems.length) {
      setSelectedIndex(Math.max(0, allItems.length - 1));
    }
  }, [allItems.length, selectedIndex]);

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const selectedEl = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
    if (selectedEl) {
      selectedEl.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  const executeItem = useCallback((item: PaletteItem) => {
    onClose();
    if (item.type === 'command') {
      item.action();
    } else {
      navigate(`/chat/${item.sessionId}`);
    }
  }, [onClose, navigate]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, allItems.length));
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + allItems.length) % Math.max(1, allItems.length));
      return;
    }

    if (e.key === 'Enter') {
      e.preventDefault();
      if (allItems[selectedIndex]) {
        executeItem(allItems[selectedIndex]);
      }
      return;
    }
  }, [allItems, selectedIndex, onClose, executeItem]);

  if (!isOpen) return null;

  // Determine group boundaries for rendering headers
  const commandCount = filteredCommands.length;
  const sessionCount = sessionItems.length;

  return (
    <div
      data-name="command-palette"
      className="fixed inset-0 z-50 flex justify-center"
      style={{ paddingTop: '20vh' }}
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" />

      {/* Dialog */}
      <div
        className="relative w-full max-w-lg mx-4 h-fit bg-white dark:bg-gray-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input */}
        <div className="flex items-center px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <MagnifyingGlassIcon className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Search conversations or type a command..."
            className="flex-1 ml-3 bg-transparent text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 outline-none"
          />
          <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 text-xs font-mono text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-700 rounded border border-gray-200 dark:border-gray-600">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-96 overflow-y-auto">
          {allItems.length === 0 && !loading ? (
            <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              No results found
            </div>
          ) : (
            <>
              {/* Commands Group */}
              {commandCount > 0 && (
                <>
                  <div className="px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Commands
                  </div>
                  {filteredCommands.map((cmd, i) => {
                    const globalIndex = i;
                    return (
                      <div
                        key={cmd.id}
                        data-index={globalIndex}
                        className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                          selectedIndex === globalIndex
                            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                        }`}
                        onClick={() => executeItem(cmd)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                      >
                        <span className="flex-shrink-0 text-gray-400 dark:text-gray-500">{cmd.icon}</span>
                        <span className="text-sm">{cmd.label}</span>
                      </div>
                    );
                  })}
                </>
              )}

              {/* Sessions Group */}
              {sessionCount > 0 && (
                <>
                  <div className="px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    Conversations
                  </div>
                  {sessionItems.map((item, i) => {
                    const globalIndex = commandCount + i;
                    return (
                      <div
                        key={item.id}
                        data-index={globalIndex}
                        className={`flex items-start gap-3 px-4 py-2.5 cursor-pointer transition-colors ${
                          selectedIndex === globalIndex
                            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                            : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50'
                        }`}
                        onClick={() => executeItem(item)}
                        onMouseEnter={() => setSelectedIndex(globalIndex)}
                      >
                        <ChatBubbleLeftIcon className="h-4 w-4 mt-0.5 flex-shrink-0 text-gray-400 dark:text-gray-500" />
                        <div className="min-w-0 flex-1">
                          <div className="text-sm truncate">{item.title}</div>
                          {item.matchType === 'content' && (
                            <div className="text-xs text-gray-400 dark:text-gray-500 truncate mt-0.5">
                              {item.matchContext}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </>
              )}

              {/* Loading indicator */}
              {loading && (
                <div className="px-4 py-3 text-center text-sm text-gray-400 dark:text-gray-500">
                  Searching...
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-3">
          <span>Arrow keys to navigate</span>
          <span>Enter to select</span>
          <span>Esc to close</span>
        </div>
      </div>
    </div>
  );
};
