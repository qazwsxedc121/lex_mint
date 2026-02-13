/**
 * ProjectManagement component - Modal interface for managing projects
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PlusIcon, PencilIcon, TrashIcon, XMarkIcon } from '@heroicons/react/24/outline';
import type { Project, ProjectCreate, ProjectUpdate } from '../../../types/project';
import { BackendDirectoryPicker } from './BackendDirectoryPicker';

interface ProjectManagementProps {
  projects: Project[];
  onCreateProject: (project: ProjectCreate) => Promise<void>;
  onUpdateProject: (id: string, project: ProjectUpdate) => Promise<void>;
  onDeleteProject: (id: string) => Promise<void>;
  initialCreateForm?: boolean;
  onClose: () => void;
}

export const ProjectManagement: React.FC<ProjectManagementProps> = ({
  projects,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  initialCreateForm = false,
  onClose,
}) => {
  const { t } = useTranslation('projects');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(initialCreateForm);
  const [formData, setFormData] = useState<Partial<ProjectCreate>>({});
  const [showDirectoryPicker, setShowDirectoryPicker] = useState(false);

  const handleEdit = (project: Project) => {
    setEditingId(project.id);
    setFormData({
      name: project.name,
      root_path: project.root_path,
      description: project.description,
    });
    setShowCreateForm(false);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setFormData({});
  };

  const handleDirectorySelect = (path: string) => {
    const trimmedName = (formData.name || '').trim();
    const normalizedPath = path.replace(/[/\\]+$/, '');
    const defaultName = normalizedPath.split(/[/\\]/).pop() || '';

    setFormData({
      ...formData,
      root_path: path,
      name: trimmedName ? formData.name : defaultName,
    });
  };

  const handleSave = async () => {
    try {
      if (editingId) {
        await onUpdateProject(editingId, formData as ProjectUpdate);
        setEditingId(null);
      } else {
        if (!formData.name || !formData.root_path) {
          alert(t('management.alert.requiredFields'));
          return;
        }
        await onCreateProject(formData as ProjectCreate);
        setShowCreateForm(false);
      }
      setFormData({});
    } catch (err) {
      alert(t('management.alert.saveFailed', { error: err instanceof Error ? err.message : 'Unknown error' }));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('management.confirm.delete'))) return;
    try {
      await onDeleteProject(id);
    } catch (err) {
      alert(t('management.alert.deleteFailed', { error: err instanceof Error ? err.message : 'Unknown error' }));
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-4xl p-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium text-gray-900 dark:text-white">
              {t('management.title')}
            </h3>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          {/* Create Button */}
          <div className="mb-4">
            <button
              onClick={() => {
                setShowCreateForm(true);
                setEditingId(null);
                setFormData({});
              }}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
            >
              <PlusIcon className="h-4 w-4" />
              {t('management.addButton')}
            </button>
          </div>

          {/* Projects Table */}
          <div className="overflow-x-auto mb-4">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t('management.table.name')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t('management.table.rootPath')}
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t('management.table.description')}
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                    {t('management.table.actions')}
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                {projects.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-6 py-4 text-center text-gray-500 dark:text-gray-400">
                      {t('management.emptyState')}
                    </td>
                  </tr>
                ) : (
                  projects.map((project) => (
                    <tr key={project.id} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white">
                        {project.name}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs">
                        {project.root_path}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400 truncate max-w-xs">
                        {project.description || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleEdit(project)}
                            className="text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
                            title={t('management.action.edit')}
                          >
                            <PencilIcon className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDelete(project.id)}
                            className="text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300"
                            title={t('management.action.delete')}
                          >
                            <TrashIcon className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Create/Edit Form Modal */}
          {(showCreateForm || editingId) && (
            <div className="fixed inset-0 z-50 overflow-y-auto">
              <div
                className="fixed inset-0 bg-black bg-opacity-50"
                onClick={() => {
                  handleCancelEdit();
                  setShowCreateForm(false);
                }}
              />
              <div className="flex min-h-full items-center justify-center p-4">
                <div className="relative bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md p-6">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                    {editingId ? t('management.modal.titleEdit') : t('management.modal.titleAdd')}
                  </h3>
                  <form onSubmit={(e) => { e.preventDefault(); handleSave(); }} className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t('management.form.nameLabel')}
                      </label>
                      <input
                        type="text"
                        required
                        maxLength={100}
                        value={formData.name || ''}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        placeholder={t('management.form.namePlaceholder')}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t('management.form.pathLabel')}
                      </label>
                      <div className="flex gap-2" data-name="project-root-path">
                        <input
                          type="text"
                          required
                          value={formData.root_path || ''}
                          onChange={(e) => setFormData({ ...formData, root_path: e.target.value })}
                          className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                          placeholder={t('management.form.pathPlaceholder')}
                        />
                        <button
                          type="button"
                          onClick={() => setShowDirectoryPicker(true)}
                          className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                        >
                          {t('management.form.browseButton')}
                        </button>
                      </div>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {t('management.form.pathHint')}
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                        {t('management.form.descLabel')}
                      </label>
                      <textarea
                        value={formData.description || ''}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        maxLength={500}
                        rows={3}
                        className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        placeholder={t('management.form.descPlaceholder')}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {t('management.form.charCount', { count: (formData.description || '').length })}
                      </p>
                    </div>
                    <div className="flex justify-end gap-3 mt-6">
                      <button
                        type="button"
                        onClick={() => {
                          handleCancelEdit();
                          setShowCreateForm(false);
                        }}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-600 dark:hover:bg-gray-600"
                      >
                        {t('common:cancel')}
                      </button>
                      <button
                        type="submit"
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                      >
                        {editingId ? t('common:save') : t('common:create')}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            </div>
          )}

          <BackendDirectoryPicker
            isOpen={showDirectoryPicker}
            initialPath={formData.root_path}
            onClose={() => setShowDirectoryPicker(false)}
            onSelect={handleDirectorySelect}
          />
        </div>
      </div>
    </div>
  );
};
