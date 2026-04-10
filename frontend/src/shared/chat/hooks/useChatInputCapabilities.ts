import { useEffect, useState } from 'react';
import type { i18n as I18nInstance } from 'i18next';

import { getToolCatalog } from '../../../services/api';
import type { ProjectChatCapabilityItem } from '../../../types/project';
import type { ChatAPI } from '../services/interfaces';

export interface InputCapabilityToggle {
  id: string;
  title: string;
  description: string;
  icon?: string | null;
}

export interface InputCapabilitySelect {
  id: string;
  title: string;
  description: string;
  icon?: string | null;
  argKey: string;
  defaultValue: string;
  options: Array<{
    value: string;
    label: string;
    description?: string;
  }>;
}

export const useChatInputCapabilities = (api: ChatAPI, i18n: I18nInstance) => {
  const [enabledContextCapabilities, setEnabledContextCapabilities] = useState<string[]>([]);
  const [contextCapabilityArgs, setContextCapabilityArgs] = useState<Record<string, Record<string, unknown>>>({});
  const [inputCapabilityToggles, setInputCapabilityToggles] = useState<InputCapabilityToggle[]>([]);
  const [inputCapabilitySelects, setInputCapabilitySelects] = useState<InputCapabilitySelect[]>([]);

  useEffect(() => {
    let cancelled = false;
    const loadChatInputCapabilities = async () => {
      try {
        const capabilities = api.getChatInputCapabilities
          ? await api.getChatInputCapabilities()
          : (await getToolCatalog()).chat_capabilities;
        if (cancelled) {
          return;
        }

        const visibleCapabilities = (Array.isArray(capabilities) ? capabilities : [])
          .filter((item: ProjectChatCapabilityItem) => item.visible_in_input)
          .sort((a: ProjectChatCapabilityItem, b: ProjectChatCapabilityItem) => {
            if (a.order !== b.order) {
              return a.order - b.order;
            }
            return a.id.localeCompare(b.id);
          });
        const toggleCapabilities = visibleCapabilities.filter(
          (item: ProjectChatCapabilityItem) => (item.control_type || 'toggle') !== 'select'
        );
        const selectCapabilities = visibleCapabilities.filter(
          (item: ProjectChatCapabilityItem) => (item.control_type || 'toggle') === 'select'
        );
        setInputCapabilityToggles(
          toggleCapabilities.map((item: ProjectChatCapabilityItem) => ({
            id: item.id,
            title: i18n.t(item.title_i18n_key, { ns: 'projects', defaultValue: item.id }),
            description: i18n.t(item.description_i18n_key, {
              ns: 'projects',
              defaultValue: item.id,
            }),
            icon: item.icon,
          }))
        );
        setInputCapabilitySelects(
          selectCapabilities
            .map((item: ProjectChatCapabilityItem) => {
              const rawOptions = Array.isArray(item.options) ? item.options : [];
              const options = rawOptions
                .filter((option) => option && typeof option.value === 'string')
                .map((option) => ({
                  value: option.value,
                  label: i18n.t(option.label_i18n_key, { ns: 'projects', defaultValue: option.value }),
                  description: option.description_i18n_key
                    ? i18n.t(option.description_i18n_key, { ns: 'projects', defaultValue: option.value })
                    : undefined,
                }));
              if (options.length === 0) {
                return null;
              }
              const defaultCandidate = typeof item.default_value === 'string'
                ? item.default_value
                : options[0].value;
              const defaultValue = options.some((option) => option.value === defaultCandidate)
                ? defaultCandidate
                : options[0].value;
              return {
                id: item.id,
                title: i18n.t(item.title_i18n_key, { ns: 'projects', defaultValue: item.id }),
                description: i18n.t(item.description_i18n_key, {
                  ns: 'projects',
                  defaultValue: item.id,
                }),
                icon: item.icon,
                argKey: item.arg_key || 'value',
                defaultValue,
                options,
              };
            })
            .filter((item): item is NonNullable<typeof item> => item !== null)
        );
        setEnabledContextCapabilities((prev) => {
          const toggleIds = new Set(toggleCapabilities.map((item) => item.id));
          const alwaysEnabledSelectIds = selectCapabilities.map((item) => item.id);
          const visibleIds = new Set(visibleCapabilities.map((item) => item.id));
          if (prev.length > 0) {
            const kept = prev.filter((item) => visibleIds.has(item) && (toggleIds.has(item) || alwaysEnabledSelectIds.includes(item)));
            const merged = new Set([...kept, ...alwaysEnabledSelectIds]);
            return Array.from(merged);
          }
          const defaults = toggleCapabilities
            .filter((item) => item.default_enabled)
            .map((item) => item.id);
          return Array.from(new Set([...defaults, ...alwaysEnabledSelectIds]));
        });
        setContextCapabilityArgs((prev) => {
          const next: Record<string, Record<string, unknown>> = {};
          const visibleIds = new Set(visibleCapabilities.map((item) => item.id));
          Object.entries(prev).forEach(([capabilityId, args]) => {
            if (visibleIds.has(capabilityId)) {
              next[capabilityId] = args;
            }
          });
          selectCapabilities.forEach((item) => {
            const options = Array.isArray(item.options) ? item.options : [];
            if (options.length === 0) {
              return;
            }
            const argKey = item.arg_key || 'value';
            const allowedValues = new Set(options.map((option) => option.value));
            const fallbackValue = (
              typeof item.default_value === 'string' && allowedValues.has(item.default_value)
            ) ? item.default_value : options[0].value;
            const currentArgs = next[item.id] || {};
            const currentRaw = currentArgs[argKey];
            const currentValue = typeof currentRaw === 'string' ? currentRaw : '';
            const selected = allowedValues.has(currentValue) ? currentValue : fallbackValue;
            next[item.id] = { ...currentArgs, [argKey]: selected };
          });
          return next;
        });
      } catch {
        if (!cancelled) {
          setInputCapabilityToggles([]);
          setInputCapabilitySelects([]);
          setEnabledContextCapabilities([]);
          setContextCapabilityArgs({});
        }
      }
    };
    void loadChatInputCapabilities();
    return () => {
      cancelled = true;
    };
  }, [api, i18n, i18n.resolvedLanguage]);

  return {
    contextCapabilityArgs,
    enabledContextCapabilities,
    inputCapabilitySelects,
    inputCapabilityToggles,
    setContextCapabilityArgs,
    setEnabledContextCapabilities,
  };
};
