/**
 * DeveloperModule - Entry point for developer tools
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '../settings/components/common';
import { useDeveloperMode } from '../../hooks/useDeveloperMode';
import { ChunkInspector } from './ChunkInspector';

export const DeveloperModule: React.FC = () => {
  const { enabled } = useDeveloperMode();

  return (
    <div className="flex flex-1 bg-gray-100 dark:bg-gray-900" data-name="developer-module">
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <PageHeader
              title="Developer Tools"
              description="Inspect chunking output and RAG diagnostics"
              actions={(
                <Link
                  to="/settings/developer"
                  className="inline-flex items-center rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600"
                >
                  Developer Settings
                </Link>
              )}
            />

            {!enabled ? (
              <div
                className="rounded-lg border border-dashed border-gray-300 dark:border-gray-700 p-6 text-sm text-gray-600 dark:text-gray-300"
                data-name="developer-mode-disabled"
              >
                Developer mode is disabled. Enable it in settings to access chunk inspection tools.
              </div>
            ) : (
              <ChunkInspector />
            )}
          </div>
        </div>
      </main>
    </div>
  );
};
