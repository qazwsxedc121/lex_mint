import { useEffect, useState } from 'react';

type EditorFontSize = 'small' | 'medium' | 'large';

const LINE_WRAPPING_KEY = 'editor-line-wrapping';
const LINE_NUMBERS_KEY = 'editor-line-numbers';
const FONT_SIZE_KEY = 'editor-font-size';
const AUTO_SAVE_BEFORE_SEND_KEY = 'project-agent-auto-save-before-send';

const readBooleanPreference = (key: string, fallback: boolean): boolean => {
  const value = localStorage.getItem(key);
  if (value === null) {
    return fallback;
  }
  return value === 'true';
};

const readFontSizePreference = (): EditorFontSize => {
  const value = localStorage.getItem(FONT_SIZE_KEY);
  if (value === 'small' || value === 'medium' || value === 'large') {
    return value;
  }
  return 'medium';
};

export function useEditorPreferences() {
  const [lineWrapping, setLineWrapping] = useState<boolean>(() => readBooleanPreference(LINE_WRAPPING_KEY, true));
  const [lineNumbers, setLineNumbers] = useState<boolean>(() => readBooleanPreference(LINE_NUMBERS_KEY, true));
  const [fontSize, setFontSize] = useState<EditorFontSize>(() => readFontSizePreference());
  const [autoSaveBeforeAgentSend, setAutoSaveBeforeAgentSend] = useState<boolean>(() =>
    readBooleanPreference(AUTO_SAVE_BEFORE_SEND_KEY, false)
  );

  useEffect(() => {
    localStorage.setItem(LINE_WRAPPING_KEY, lineWrapping ? 'true' : 'false');
  }, [lineWrapping]);

  useEffect(() => {
    localStorage.setItem(LINE_NUMBERS_KEY, lineNumbers ? 'true' : 'false');
  }, [lineNumbers]);

  useEffect(() => {
    localStorage.setItem(FONT_SIZE_KEY, fontSize);
  }, [fontSize]);

  useEffect(() => {
    localStorage.setItem(AUTO_SAVE_BEFORE_SEND_KEY, autoSaveBeforeAgentSend ? 'true' : 'false');
  }, [autoSaveBeforeAgentSend]);

  return {
    lineWrapping,
    setLineWrapping,
    lineNumbers,
    setLineNumbers,
    fontSize,
    setFontSize,
    autoSaveBeforeAgentSend,
    setAutoSaveBeforeAgentSend,
  };
}
