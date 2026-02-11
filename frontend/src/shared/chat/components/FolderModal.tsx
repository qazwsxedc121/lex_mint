/**
 * FolderModal - Create/Edit folder modal
 */

import React, { useState, useEffect } from 'react';

interface FolderModalProps {
  isOpen: boolean;
  mode: 'create' | 'edit';
  initialName?: string;
  onConfirm: (name: string) => Promise<boolean>;
  onClose: () => void;
}

export const FolderModal: React.FC<FolderModalProps> = ({
  isOpen,
  mode,
  initialName = '',
  onConfirm,
  onClose,
}) => {
  const [name, setName] = useState(initialName);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setName(initialName);
  }, [initialName, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || submitting) return;

    setSubmitting(true);
    const success = await onConfirm(name.trim());
    setSubmitting(false);

    if (success) {
      setName('');
      onClose();
    }
  };

  const handleClose = () => {
    if (!submitting) {
      setName('');
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 w-96">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {mode === 'create' ? 'Create Folder' : 'Rename Folder'}
        </h2>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Folder name"
            className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            autoFocus
            disabled={submitting}
          />

          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={handleClose}
              disabled={submitting}
              className="px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || submitting}
              className="px-4 py-2 text-sm bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Saving...' : mode === 'create' ? 'Create' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
