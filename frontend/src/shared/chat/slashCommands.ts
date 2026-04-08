export interface SlashCommandSuggestion {
  id: string;
  trigger: string;
  label: string;
  description: string;
}

interface SlashCommandDefinition {
  id: string;
  trigger: string;
  labelKey: string;
  descriptionKey: string;
}

const SLASH_COMMAND_DEFINITIONS: SlashCommandDefinition[] = [
  {
    id: 'btw',
    trigger: 'btw',
    labelKey: 'input.slashCommandBtwLabel',
    descriptionKey: 'input.slashCommandBtwDescription',
  },
];

const BTW_COMMAND_PREFIX = /^\/btw(?:\s+|$)/i;

export function buildSlashCommandSuggestions(
  query: string,
  t: (key: string) => string,
): SlashCommandSuggestion[] {
  const normalizedQuery = query.trim().toLowerCase();
  const suggestions = SLASH_COMMAND_DEFINITIONS.map((command) => ({
    id: command.id,
    trigger: command.trigger,
    label: t(command.labelKey),
    description: t(command.descriptionKey),
  }));

  if (!normalizedQuery) {
    return suggestions;
  }

  return suggestions.filter((command) => (
    command.trigger.includes(normalizedQuery) || command.label.toLowerCase().includes(normalizedQuery)
  ));
}

export function applyOutgoingSlashCommandEffects(message: string): { temporaryTurn: boolean; strippedMessage: string } {
  if (!BTW_COMMAND_PREFIX.test(message)) {
    return { temporaryTurn: false, strippedMessage: message };
  }

  const stripped = message.replace(/^\/btw\b/i, '').trimStart();
  return { temporaryTurn: true, strippedMessage: stripped };
}

