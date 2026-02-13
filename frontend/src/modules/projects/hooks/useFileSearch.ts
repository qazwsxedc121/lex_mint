import { useState, useEffect } from 'react';
import { searchProjectFiles } from '../../../services/api';
import type { FileSearchResult } from '../../../services/api';

const toCurrentFileResult = (filePath: string): FileSearchResult => {
  const normalizedPath = filePath.replace(/\\/g, '/');
  const pathParts = normalizedPath.split('/');
  const name = pathParts[pathParts.length - 1] || normalizedPath;
  const dotIndex = name.lastIndexOf('.');
  const extension = dotIndex >= 0 ? name.slice(dotIndex) : '';
  const directory = pathParts.length > 1 ? pathParts.slice(0, -1).join('/') : '';

  return {
    path: normalizedPath,
    name,
    directory,
    extension,
    score: 9999,
    proximityReason: 'same-dir',
  };
};

/**
 * Hook for debounced file search with proximity scoring
 *
 * @param projectId - Current project ID
 * @param currentFile - Current file path for proximity calculation
 * @returns Search query setter, results, and loading state
 */
export function useFileSearch(projectId: string | null, currentFile?: string | null) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<FileSearchResult[]>([]);
  const [loading, setLoading] = useState(false);

  // Debounced search effect (300ms delay, similar to CommandPalette pattern)
  useEffect(() => {
    if (!projectId) {
      setResults([]);
      setLoading(false);
      return;
    }

    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setResults(currentFile ? [toCurrentFileResult(currentFile)] : []);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timeoutId = setTimeout(async () => {
      try {
        const searchResults = await searchProjectFiles(
          projectId,
          trimmedQuery,
          currentFile
        );
        setResults(searchResults);
      } catch (error) {
        console.error('File search failed:', error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [projectId, query, currentFile]);

  return { query, setQuery, results, loading };
}
