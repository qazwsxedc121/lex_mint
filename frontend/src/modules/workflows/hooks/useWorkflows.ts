import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import type { Workflow, WorkflowCreate, WorkflowRunRecord, WorkflowUpdate } from '../../../types/workflow';
import * as api from '../../../services/api';
import i18n from '../../../i18n';

const parseApiError = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message;
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

const buildMvpWorkflow = (): WorkflowCreate => ({
  name: i18n.t('workflow:defaults.newWorkflowName'),
  description: i18n.t('workflow:defaults.newWorkflowDescription'),
  enabled: true,
  input_schema: [
    { key: 'input', type: 'string', required: true, description: 'Main input text' },
  ],
  entry_node_id: 'start_1',
  nodes: [
    { id: 'start_1', type: 'start', next_id: 'llm_1' },
    { id: 'llm_1', type: 'llm', prompt_template: '{{inputs.input}}', output_key: 'answer', next_id: 'end_1' },
    { id: 'end_1', type: 'end', result_template: '{{ctx.answer}}' },
  ],
});

export function useWorkflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
      if (data.length === 0) {
        setSelectedWorkflowId(null);
        setRuns([]);
      } else {
        setSelectedWorkflowId((previous) => {
        if (previous && data.some((item) => item.id === previous)) {
          return previous;
        }
        return data[0].id;
        });
      }
    } catch (err) {
      setError(parseApiError(err, i18n.t('workflow:errors.loadWorkflows')));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshWorkflows();
  }, [refreshWorkflows]);

  const refreshRuns = useCallback(async (workflowId: string): Promise<WorkflowRunRecord[]> => {
    try {
      const data = await api.listWorkflowRuns(workflowId, 50);
      setRuns(data);
      return data;
    } catch (err) {
      setError(parseApiError(err, i18n.t('workflow:errors.loadRunHistory')));
      return [];
    }
  }, []);

  useEffect(() => {
    if (!selectedWorkflowId) {
      setRuns([]);
      return;
    }
    refreshRuns(selectedWorkflowId);
  }, [refreshRuns, selectedWorkflowId]);

  const createWorkflow = useCallback(async (payload?: WorkflowCreate) => {
    setSaving(true);
    setError(null);
    try {
      const workflowId = await api.createWorkflow(payload ?? buildMvpWorkflow());
      await refreshWorkflows();
      setSelectedWorkflowId(workflowId);
      return workflowId;
    } catch (err) {
      setError(parseApiError(err, i18n.t('workflow:errors.createWorkflow')));
      throw err;
    } finally {
      setSaving(false);
    }
  }, [refreshWorkflows]);

  const updateWorkflow = useCallback(async (workflowId: string, payload: WorkflowUpdate) => {
    setSaving(true);
    setError(null);
    try {
      await api.updateWorkflow(workflowId, payload);
      await refreshWorkflows();
      if (workflowId === selectedWorkflowId) {
        await refreshRuns(workflowId);
      }
    } catch (err) {
      setError(parseApiError(err, i18n.t('workflow:errors.updateWorkflow')));
      throw err;
    } finally {
      setSaving(false);
    }
  }, [refreshRuns, refreshWorkflows, selectedWorkflowId]);

  const deleteWorkflow = useCallback(async (workflowId: string) => {
    setSaving(true);
    setError(null);
    try {
      await api.deleteWorkflow(workflowId);
      await refreshWorkflows();
    } catch (err) {
      setError(parseApiError(err, i18n.t('workflow:errors.deleteWorkflow')));
      throw err;
    } finally {
      setSaving(false);
    }
  }, [refreshWorkflows]);

  return {
    workflows,
    selectedWorkflowId,
    setSelectedWorkflowId,
    runs,
    loading,
    saving,
    error,
    createWorkflow,
    updateWorkflow,
    deleteWorkflow,
    refreshWorkflows,
    refreshRuns,
  };
}
