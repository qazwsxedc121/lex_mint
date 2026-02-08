/**
 * useTTS hook - Text-to-Speech with Edge TTS + browser fallback
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { synthesizeSpeech } from '../../../services/api';
import type { MutableRefObject } from 'react';

/**
 * Strip markdown/code/thinking blocks to plain speech text (client-side).
 */
function sanitizeForSpeech(text: string): string {
  let result = text;
  // Remove <think>...</think> blocks
  result = result.replace(/<think>[\s\S]*?<\/think>/g, '');
  // Remove code fences
  result = result.replace(/```[\s\S]*?```/g, '');
  // Remove inline code
  result = result.replace(/`[^`]+`/g, '');
  // Remove image refs
  result = result.replace(/!\[[^\]]*\]\([^)]*\)/g, '');
  // Remove markdown links [text](url) -> text
  result = result.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  // Remove bold/italic markers
  result = result.replace(/[*_]{1,3}/g, '');
  // Remove strikethrough
  result = result.replace(/~~/g, '');
  // Remove heading markers
  result = result.replace(/^#{1,6}\s+/gm, '');
  // Remove HTML tags
  result = result.replace(/<[^>]+>/g, '');
  // Remove blockquote markers
  result = result.replace(/^>\s*/gm, '');
  // Remove horizontal rules
  result = result.replace(/^[-*_]{3,}\s*$/gm, '');
  // Remove list markers
  result = result.replace(/^\s*[-*+]\s+/gm, '');
  result = result.replace(/^\s*\d+\.\s+/gm, '');
  // Collapse whitespace
  result = result.replace(/\n{3,}/g, '\n\n');
  result = result.replace(/[ \t]+/g, ' ');
  return result.trim();
}

export function useTTS() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  const cleanup = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current = null;
    }
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
  }, []);

  const stop = useCallback(() => {
    cleanup();
    setIsPlaying(false);
    setIsLoading(false);
  }, [cleanup]);

  const fallbackToWebSpeech = useCallback((text: string) => {
    if (!window.speechSynthesis) {
      setIsPlaying(false);
      return;
    }

    const sanitized = sanitizeForSpeech(text);
    if (!sanitized) {
      setIsPlaying(false);
      return;
    }

    // Chrome has a bug where utterances longer than ~15s get cut off.
    // Split into sentences to work around this.
    const sentences = sanitized.match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [sanitized];
    const chunks: string[] = [];
    let current = '';

    for (const sentence of sentences) {
      if ((current + sentence).length > 200) {
        if (current) chunks.push(current.trim());
        current = sentence;
      } else {
        current += sentence;
      }
    }
    if (current.trim()) chunks.push(current.trim());

    let chunkIndex = 0;

    function speakNext() {
      if (chunkIndex >= chunks.length) {
        setIsPlaying(false);
        return;
      }
      const utterance = new SpeechSynthesisUtterance(chunks[chunkIndex]);
      utterance.onend = () => {
        chunkIndex++;
        speakNext();
      };
      utterance.onerror = () => {
        setIsPlaying(false);
      };
      window.speechSynthesis.speak(utterance);
    }

    speakNext();
    setIsPlaying(true);
  }, []);

  const speak = useCallback(async (text: string) => {
    stop();
    setIsLoading(true);

    try {
      const blob = await synthesizeSpeech(text, undefined, abortRef as MutableRefObject<AbortController | null>);

      // Check if we got actual audio data
      if (blob.size === 0) {
        fallbackToWebSpeech(text);
        return;
      }

      const url = URL.createObjectURL(blob);
      blobUrlRef.current = url;

      const audio = new Audio(url);
      audio.onended = () => {
        setIsPlaying(false);
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
          blobUrlRef.current = null;
        }
      };
      audio.onerror = () => {
        // If audio playback fails, fall back to browser TTS
        if (blobUrlRef.current) {
          URL.revokeObjectURL(blobUrlRef.current);
          blobUrlRef.current = null;
        }
        fallbackToWebSpeech(text);
      };
      audioRef.current = audio;
      await audio.play();
      setIsPlaying(true);
    } catch (err) {
      // Network error or backend unavailable - fall back to browser TTS
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled, don't fallback
        return;
      }
      fallbackToWebSpeech(text);
    } finally {
      setIsLoading(false);
    }
  }, [stop, fallbackToWebSpeech]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanup();
    };
  }, [cleanup]);

  return { isPlaying, isLoading, speak, stop };
}
