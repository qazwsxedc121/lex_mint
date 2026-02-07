/**
 * ParamOverridePopover - Per-session parameter override popover.
 *
 * Allows users to temporarily override assistant parameters for the current chat session.
 * Overrides are saved to the session's YAML frontmatter and persist across page refreshes.
 *
 * Uses local draft state + debounced save to avoid rapid concurrent file writes.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { AdjustmentsHorizontalIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { useChatServices } from '../services/ChatServiceProvider';
import { listModels, listProviders } from '../../../services/api';
import { PARAM_SUPPORT } from '../../constants/paramSupport';
import type { ParamOverrides } from '../../../types/message';
import type { Assistant } from '../../../types/assistant';
import type { Model, Provider } from '../../../types/model';

interface ParamOverridePopoverProps {
  sessionId: string;
  currentAssistantId?: string;
  paramOverrides: ParamOverrides;
  onOverridesChange: (overrides: ParamOverrides) => void;
  hasActiveOverrides: boolean;
}

interface SliderFieldConfig {
  key: keyof ParamOverrides;
  label: string;
  min: number;
  max: number;
  step: number;
  formatValue: (v: number) => string;
}

const SLIDER_FIELDS: SliderFieldConfig[] = [
  { key: 'temperature', label: 'Temperature', min: 0, max: 2, step: 0.1, formatValue: (v) => v.toFixed(1) },
  { key: 'max_tokens', label: 'Max Tokens', min: 1, max: 8192, step: 1, formatValue: (v) => Math.round(v).toString() },
  { key: 'top_p', label: 'Top P', min: 0, max: 1, step: 0.05, formatValue: (v) => v.toFixed(2) },
  { key: 'top_k', label: 'Top K', min: 1, max: 200, step: 1, formatValue: (v) => Math.round(v).toString() },
  { key: 'frequency_penalty', label: 'Frequency Penalty', min: -2, max: 2, step: 0.1, formatValue: (v) => v.toFixed(1) },
  { key: 'presence_penalty', label: 'Presence Penalty', min: -2, max: 2, step: 0.1, formatValue: (v) => v.toFixed(1) },
];

const DEBOUNCE_MS = 500;

export const ParamOverridePopover: React.FC<ParamOverridePopoverProps> = ({
  sessionId,
  currentAssistantId,
  paramOverrides,
  onOverridesChange,
  hasActiveOverrides,
}) => {
  const { api } = useChatServices();
  const [isOpen, setIsOpen] = useState(false);
  const [assistant, setAssistant] = useState<Assistant | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [popoverPosition, setPopoverPosition] = useState({ top: 0, left: 0 });

  // --- Local draft state (updated instantly on slider drag) ---
  const [draft, setDraft] = useState<ParamOverrides>(paramOverrides);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const savingRef = useRef(false);

  // Sync draft from props when they change externally (e.g. session load, clear)
  useEffect(() => {
    if (!savingRef.current) {
      setDraft(paramOverrides);
    }
  }, [paramOverrides]);

  // Debounced save: flush draft to backend
  const flushToBackend = useCallback((overrides: ParamOverrides) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      savingRef.current = true;
      onOverridesChange(overrides);
      // Reset saving flag after a tick so the next props sync isn't blocked
      setTimeout(() => { savingRef.current = false; }, 200);
    }, DEBOUNCE_MS);
  }, [onOverridesChange]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Load data when popover opens
  useEffect(() => {
    if (!isOpen) return;

    const loadData = async () => {
      try {
        const [modelsData, providersData] = await Promise.all([
          listModels(),
          listProviders(),
        ]);
        setModels(modelsData.filter((m) => m.enabled));
        setProviders(providersData);

        if (currentAssistantId && !currentAssistantId.startsWith('__legacy_model_')) {
          const assistantData = await api.getAssistant(currentAssistantId);
          setAssistant(assistantData);
        }
      } catch (err) {
        console.error('Failed to load param override data:', err);
      }
    };
    loadData();
  }, [isOpen, currentAssistantId, api]);

  // Update popover position
  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPopoverPosition({
        top: rect.top,
        left: rect.left,
      });
    }
  }, [isOpen]);

  // Determine the effective model (overridden or assistant default)
  const effectiveModelId = draft.model_id || assistant?.model_id;
  const effectiveProviderId = effectiveModelId?.split(':')[0];
  const effectiveProvider = providers.find((p) => p.id === effectiveProviderId);
  const sdkClass = effectiveProvider?.sdk_class || effectiveProvider?.protocol || 'openai';

  const supportsParam = (paramKey: string): boolean => {
    const supported = PARAM_SUPPORT[paramKey];
    if (!supported) return true; // temperature, max_rounds always shown
    return supported.includes(sdkClass);
  };

  const handleFieldChange = (key: keyof ParamOverrides, value: number | string) => {
    const newDraft = { ...draft, [key]: value };
    setDraft(newDraft);
    flushToBackend(newDraft);
  };

  const handleClearField = (key: keyof ParamOverrides) => {
    const newDraft = { ...draft };
    delete newDraft[key];
    setDraft(newDraft);
    flushToBackend(newDraft);
  };

  const handleClearAll = () => {
    const empty: ParamOverrides = {};
    setDraft(empty);
    // Clear all: save immediately (no debounce)
    if (debounceRef.current) clearTimeout(debounceRef.current);
    onOverridesChange(empty);
  };

  // For model and max_rounds changes, save immediately (not slider-based)
  const handleImmediateChange = (overrides: ParamOverrides) => {
    setDraft(overrides);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    onOverridesChange(overrides);
  };

  const getAssistantDefault = (key: keyof ParamOverrides): number | string | null | undefined => {
    if (!assistant) return undefined;
    switch (key) {
      case 'model_id': return assistant.model_id;
      case 'temperature': return assistant.temperature;
      case 'max_tokens': return assistant.max_tokens;
      case 'top_p': return assistant.top_p;
      case 'top_k': return assistant.top_k;
      case 'frequency_penalty': return assistant.frequency_penalty;
      case 'presence_penalty': return assistant.presence_penalty;
      case 'max_rounds': return assistant.max_rounds;
      default: return undefined;
    }
  };

  const hasDraftOverrides = Object.keys(draft).length > 0;

  return (
    <div data-name="param-override-root">
      {/* Trigger button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center justify-center p-1.5 rounded-md border transition-colors ${
          hasActiveOverrides || hasDraftOverrides
            ? 'bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-800'
            : 'bg-gray-50 dark:bg-gray-700 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-600'
        }`}
        title={hasActiveOverrides ? 'Parameter overrides active' : 'Override parameters'}
      >
        <AdjustmentsHorizontalIcon className="h-4 w-4" />
      </button>

      {/* Popover - rendered via Portal */}
      {isOpen && createPortal(
        <>
          {/* Overlay */}
          <div
            className="fixed inset-0 z-[100]"
            onClick={() => setIsOpen(false)}
          />

          {/* Popover content */}
          <div
            data-name="param-override-popover"
            className="fixed bg-white dark:bg-gray-800 rounded-lg shadow-xl z-[101] border border-gray-200 dark:border-gray-700 w-80 max-h-[70vh] overflow-y-auto"
            style={{
              top: `${popoverPosition.top - 8}px`,
              left: `${popoverPosition.left}px`,
              transform: 'translateY(-100%)',
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                Parameter Overrides
              </h3>
              {hasDraftOverrides && (
                <button
                  onClick={handleClearAll}
                  className="text-xs text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                >
                  Clear All
                </button>
              )}
            </div>

            <div className="p-4 space-y-4">
              {/* Model selector */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    Model
                  </label>
                  {draft.model_id && (
                    <button
                      onClick={() => {
                        const newDraft = { ...draft };
                        delete newDraft.model_id;
                        handleImmediateChange(newDraft);
                      }}
                      className="p-0.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
                      title="Clear override"
                    >
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  )}
                </div>
                <select
                  value={draft.model_id || ''}
                  onChange={(e) => {
                    if (e.target.value) {
                      handleImmediateChange({ ...draft, model_id: e.target.value });
                    } else {
                      const newDraft = { ...draft };
                      delete newDraft.model_id;
                      handleImmediateChange(newDraft);
                    }
                  }}
                  className="w-full text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5"
                >
                  <option value="">
                    {assistant ? `Default (${assistant.model_id})` : 'Default'}
                  </option>
                  {models.map((m) => (
                    <option key={`${m.provider_id}:${m.id}`} value={`${m.provider_id}:${m.id}`}>
                      {m.name} ({m.provider_id}:{m.id})
                    </option>
                  ))}
                </select>
              </div>

              {/* Temperature (always shown) */}
              <SliderField
                label="Temperature"
                value={draft.temperature}
                defaultValue={getAssistantDefault('temperature') as number | undefined}
                min={0}
                max={2}
                step={0.1}
                formatValue={(v) => v.toFixed(1)}
                onChange={(v) => handleFieldChange('temperature', v)}
                onClear={() => handleClearField('temperature')}
              />

              {/* Conditional slider fields */}
              {SLIDER_FIELDS.filter((f) => f.key !== 'temperature').map((field) => {
                if (!supportsParam(field.key)) return null;
                return (
                  <SliderField
                    key={field.key}
                    label={field.label}
                    value={draft[field.key] as number | undefined}
                    defaultValue={getAssistantDefault(field.key) as number | undefined}
                    min={field.min}
                    max={field.max}
                    step={field.step}
                    formatValue={field.formatValue}
                    onChange={(v) => handleFieldChange(field.key, v)}
                    onClear={() => handleClearField(field.key)}
                  />
                );
              })}

              {/* Max Rounds */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    Max Rounds
                  </label>
                  {draft.max_rounds !== undefined && (
                    <button
                      onClick={() => {
                        const newDraft = { ...draft };
                        delete newDraft.max_rounds;
                        handleImmediateChange(newDraft);
                      }}
                      className="p-0.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
                      title="Clear override"
                    >
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  )}
                </div>
                <input
                  type="number"
                  value={draft.max_rounds ?? ''}
                  placeholder={
                    assistant?.max_rounds !== undefined && assistant?.max_rounds !== null
                      ? `Default: ${assistant.max_rounds === -1 ? 'Unlimited' : assistant.max_rounds}`
                      : 'Default: Unlimited'
                  }
                  min={-1}
                  onChange={(e) => {
                    const val = e.target.value;
                    if (val === '') {
                      const newDraft = { ...draft };
                      delete newDraft.max_rounds;
                      handleImmediateChange(newDraft);
                    } else {
                      handleImmediateChange({ ...draft, max_rounds: parseInt(val, 10) });
                    }
                  }}
                  className="w-full text-sm rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-2 py-1.5"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">-1 = unlimited</p>
              </div>
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
};

// ---- Internal SliderField component ----

interface SliderFieldProps {
  label: string;
  value: number | undefined;
  defaultValue: number | null | undefined;
  min: number;
  max: number;
  step: number;
  formatValue: (v: number) => string;
  onChange: (value: number) => void;
  onClear: () => void;
}

const SliderField: React.FC<SliderFieldProps> = ({
  label,
  value,
  defaultValue,
  min,
  max,
  step,
  formatValue,
  onChange,
  onClear,
}) => {
  const isOverridden = value !== undefined;
  const displayValue = value ?? defaultValue ?? min;

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-medium text-gray-700 dark:text-gray-300">
          {label}
        </label>
        <div className="flex items-center gap-1.5">
          <span className={`text-xs ${isOverridden ? 'text-violet-600 dark:text-violet-400 font-medium' : 'text-gray-500 dark:text-gray-400'}`}>
            {formatValue(displayValue as number)}
          </span>
          {isOverridden && (
            <button
              onClick={onClear}
              className="p-0.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400"
              title="Clear override"
            >
              <XMarkIcon className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={displayValue as number}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 rounded-lg appearance-none cursor-pointer accent-violet-600 dark:accent-violet-400 bg-gray-200 dark:bg-gray-600"
      />
      {!isOverridden && defaultValue != null && (
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
          Default: {formatValue(defaultValue as number)}
        </p>
      )}
    </div>
  );
};
