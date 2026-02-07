/**
 * Assistant icon collection using Lucide React icons
 *
 * Exposes all ~1600+ Lucide icons for assistant avatars.
 */

import type { LucideIcon } from 'lucide-react';
import { icons, Bot } from 'lucide-react';

/** Map of icon keys to Lucide icon components (all available icons) */
export const ASSISTANT_ICONS: Record<string, LucideIcon> = icons as Record<string, LucideIcon>;

/** All available icon keys (sorted alphabetically) */
export const ASSISTANT_ICON_KEYS: string[] = Object.keys(ASSISTANT_ICONS).sort();

/** Default icon key used as fallback */
export const DEFAULT_ICON_KEY = 'Bot';

/** Get the Lucide icon component for a given key. Falls back to Bot if key is invalid. */
export function getAssistantIcon(key?: string | null): LucideIcon {
  if (key && ASSISTANT_ICONS[key]) {
    return ASSISTANT_ICONS[key];
  }
  return Bot;
}

/** Pick a random icon key from the collection */
export function getRandomIconKey(): string {
  const index = Math.floor(Math.random() * ASSISTANT_ICON_KEYS.length);
  return ASSISTANT_ICON_KEYS[index];
}
