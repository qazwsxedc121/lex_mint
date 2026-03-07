import { useEffect } from 'react';

interface UseGlobalHotkeyOptions {
  key: string;
  onTrigger: () => void;
  enabled?: boolean;
}

export function useGlobalHotkey({ key, onTrigger, enabled = true }: UseGlobalHotkeyOptions) {
  useEffect(() => {
    if (!enabled) {
      return undefined;
    }

    const normalizedKey = key.toLowerCase();
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) {
        return;
      }
      if (event.key.toLowerCase() !== normalizedKey) {
        return;
      }
      event.preventDefault();
      onTrigger();
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, key, onTrigger]);
}
