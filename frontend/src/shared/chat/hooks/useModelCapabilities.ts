/**
 * Custom hook for checking model capabilities (vision, reasoning, etc.)
 */

import { useState, useEffect } from 'react';
import { useChatServices } from '../services/ChatServiceProvider';
import type { ReasoningControls } from '../../../types/model';

interface ModelCapabilities {
  supportsVision: boolean;
  supportsReasoning: boolean;
  reasoningControls: ReasoningControls | null;
  loading: boolean;
}

export function useModelCapabilities(
  targetType: 'assistant' | 'model',
  assistantId: string | null,
  modelId: string | null,
): ModelCapabilities {
  const { api } = useChatServices();
  const [supportsVision, setSupportsVision] = useState(false);
  const [supportsReasoning, setSupportsReasoning] = useState(false);
  const [reasoningControls, setReasoningControls] = useState<ReasoningControls | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const checkCapabilities = async () => {
      try {
        setLoading(true);
        let effectiveModelId: string | null = null;

        if (targetType === 'assistant') {
          if (!assistantId || assistantId.startsWith('__legacy_model_')) {
            setSupportsVision(false);
            setSupportsReasoning(false);
            setReasoningControls(null);
            return;
          }
          const assistant = await api.getAssistant(assistantId);
          effectiveModelId = assistant.model_id;
        } else {
          effectiveModelId = modelId;
        }

        if (!effectiveModelId) {
          setSupportsVision(false);
          setSupportsReasoning(false);
          setReasoningControls(null);
          return;
        }

        const response = await api.getModelCapabilities(effectiveModelId);
        setSupportsVision(response.capabilities.vision || false);
        setSupportsReasoning(response.capabilities.reasoning || false);
        setReasoningControls(response.capabilities.reasoning_controls || null);
      } catch (error) {
        console.error('Failed to check model capabilities:', error);
        setSupportsVision(false);
        setSupportsReasoning(false);
        setReasoningControls(null);
      } finally {
        setLoading(false);
      }
    };

    checkCapabilities();
  }, [targetType, assistantId, modelId, api]);

  return { supportsVision, supportsReasoning, reasoningControls, loading };
}
