/**
 * useDeveloperMode - persisted developer mode flag
 */

import { useEffect, useState } from 'react';

const STORAGE_KEY = 'developer-mode-enabled';
const EVENT_NAME = 'developer-mode-changed';

export function readDeveloperMode(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
}

export function writeDeveloperMode(enabled: boolean) {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false');
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function useDeveloperMode() {
  const [enabled, setEnabled] = useState(readDeveloperMode());

  useEffect(() => {
    const handleChange = () => {
      setEnabled(readDeveloperMode());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY) {
        setEnabled(event.newValue === 'true');
      }
    };

    window.addEventListener(EVENT_NAME, handleChange);
    window.addEventListener('storage', handleStorage);

    return () => {
      window.removeEventListener(EVENT_NAME, handleChange);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const update = (value: boolean) => {
    setEnabled(value);
    writeDeveloperMode(value);
  };

  return { enabled, setEnabled: update };
}
