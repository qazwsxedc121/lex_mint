/**
 * Custom hook for checking model capabilities (vision, reasoning, etc.)
 */

import { useState, useEffect } from 'react';
import { getAssistant, getModelCapabilities } from '../../../services/api';

interface ModelCapabilities {
  supportsVision: boolean;
  supportsReasoning: boolean;
  loading: boolean;
}

export function useModelCapabilities(assistantId: string | null): ModelCapabilities {
  const [supportsVision, setSupportsVision] = useState(false);
  const [supportsReasoning, setSupportsReasoning] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const checkCapabilities = async () => {
      if (!assistantId || assistantId.startsWith('__legacy_model_')) {
        setSupportsVision(false);
        setSupportsReasoning(false);
        return;
      }

      try {
        setLoading(true);
        const assistant = await getAssistant(assistantId);
        const modelId = assistant.model_id;

        if (!modelId) {
          setSupportsVision(false);
          setSupportsReasoning(false);
          return;
        }

        // Query model capabilities from backend
        const response = await getModelCapabilities(modelId);
        setSupportsVision(response.capabilities.vision || false);
        setSupportsReasoning(response.capabilities.reasoning || false);
      } catch (error) {
        console.error('Failed to check model capabilities:', error);
        setSupportsVision(false);
        setSupportsReasoning(false);
      } finally {
        setLoading(false);
      }
    };

    checkCapabilities();
  }, [assistantId]);

  return { supportsVision, supportsReasoning, loading };
}
