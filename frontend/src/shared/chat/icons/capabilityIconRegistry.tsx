import type { ComponentType, SVGProps } from 'react';
import * as OutlineIcons from '@heroicons/react/24/outline';

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

const FALLBACK_ICON: IconComponent = OutlineIcons.Squares2X2Icon;

const isIconComponent = (value: unknown): value is IconComponent =>
  (typeof value === 'function') || (typeof value === 'object' && value !== null);

const toPascalCase = (value: string): string => {
  const withWordBoundaries = value
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[_\-\s]+/g, ' ')
    .trim();
  if (!withWordBoundaries) {
    return '';
  }
  return withWordBoundaries
    .split(' ')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join('');
};

const resolveOutlineIconByName = (iconKey: string): IconComponent | null => {
  const raw = iconKey.trim();
  if (!raw) {
    return null;
  }
  const pascal = toPascalCase(raw);
  const candidates = new Set<string>([
    raw,
    raw.endsWith('Icon') ? raw : `${raw}Icon`,
    pascal,
    pascal.endsWith('Icon') ? pascal : `${pascal}Icon`,
  ]);
  for (const candidate of candidates) {
    const maybeIcon = (OutlineIcons as Record<string, unknown>)[candidate];
    if (isIconComponent(maybeIcon)) {
      return maybeIcon;
    }
  }
  return null;
};

export const resolveCapabilityIcon = (iconKey?: string | null): IconComponent => {
  const raw = String(iconKey || '').trim();
  if (!raw) {
    return FALLBACK_ICON;
  }
  return resolveOutlineIconByName(raw) || FALLBACK_ICON;
};
