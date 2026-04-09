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

export type SlashCommandAction = 'none' | 'insert_separator' | 'clear_all' | 'compress_context' | 'show_help' | 'show_context_diagnostics';

const SLASH_COMMAND_DEFINITIONS: SlashCommandDefinition[] = [
  {
    id: 'clear',
    trigger: 'clear',
    labelKey: 'input.slashCommandClearLabel',
    descriptionKey: 'input.slashCommandClearDescription',
  },
  {
    id: 'reset',
    trigger: 'reset',
    labelKey: 'input.slashCommandResetLabel',
    descriptionKey: 'input.slashCommandResetDescription',
  },
  {
    id: 'new',
    trigger: 'new',
    labelKey: 'input.slashCommandNewLabel',
    descriptionKey: 'input.slashCommandNewDescription',
  },
  {
    id: 'compact',
    trigger: 'compact',
    labelKey: 'input.slashCommandCompactLabel',
    descriptionKey: 'input.slashCommandCompactDescription',
  },
  {
    id: 'btw',
    trigger: 'btw',
    labelKey: 'input.slashCommandBtwLabel',
    descriptionKey: 'input.slashCommandBtwDescription',
  },
  {
    id: 'help',
    trigger: 'help',
    labelKey: 'input.slashCommandHelpLabel',
    descriptionKey: 'input.slashCommandHelpDescription',
  },
  {
    id: 'context',
    trigger: 'context',
    labelKey: 'input.slashCommandContextLabel',
    descriptionKey: 'input.slashCommandContextDescription',
  },
];

const BTW_COMMAND_PREFIX = /^\/btw(?:\s+|$)/i;
const CLEAR_COMMAND_PREFIX = /^\/clear(?:\s+|$)/i;
const RESET_COMMAND_PREFIX = /^\/reset(?:\s+|$)/i;
const NEW_COMMAND_PREFIX = /^\/new(?:\s+|$)/i;
const COMPACT_COMMAND_PREFIX = /^\/compact(?:\s+|$)/i;
const HELP_COMMAND_PREFIX = /^\/help(?:\s+|$)/i;
const CONTEXT_COMMAND_PREFIX = /^\/context(?:\s+|$)/i;

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

export function applyOutgoingSlashCommandEffects(message: string): {
  temporaryTurn: boolean;
  strippedMessage: string;
  action: SlashCommandAction;
} {
  if (HELP_COMMAND_PREFIX.test(message)) {
    return {
      temporaryTurn: true,
      strippedMessage: '',
      action: 'show_help',
    };
  }

  if (CONTEXT_COMMAND_PREFIX.test(message)) {
    return {
      temporaryTurn: true,
      strippedMessage: message.replace(/^\/context\b/i, '').trimStart(),
      action: 'show_context_diagnostics',
    };
  }

  if (COMPACT_COMMAND_PREFIX.test(message)) {
    return {
      temporaryTurn: false,
      strippedMessage: message.replace(/^\/compact\b/i, '').trimStart(),
      action: 'compress_context',
    };
  }

  if (CLEAR_COMMAND_PREFIX.test(message)) {
    return {
      temporaryTurn: false,
      strippedMessage: message.replace(/^\/clear\b/i, '').trimStart(),
      action: 'insert_separator',
    };
  }

  if (RESET_COMMAND_PREFIX.test(message) || NEW_COMMAND_PREFIX.test(message)) {
    const stripped = message
      .replace(/^\/reset\b/i, '')
      .replace(/^\/new\b/i, '')
      .trimStart();
    return {
      temporaryTurn: false,
      strippedMessage: stripped,
      action: 'clear_all',
    };
  }

  if (!BTW_COMMAND_PREFIX.test(message)) {
    return { temporaryTurn: false, strippedMessage: message, action: 'none' };
  }

  const stripped = message.replace(/^\/btw\b/i, '').trimStart();
  return { temporaryTurn: true, strippedMessage: stripped, action: 'none' };
}

export function buildSlashHelpMessage(t: (key: string) => string): string {
  const commandLines = [
    { usage: '/help', descriptionKey: 'input.slashCommandHelpDescription' },
    { usage: '/context [message]', descriptionKey: 'input.slashCommandContextDescription' },
    { usage: '/clear', descriptionKey: 'input.slashCommandClearDescription' },
    { usage: '/reset', descriptionKey: 'input.slashCommandResetDescription' },
    { usage: '/new', descriptionKey: 'input.slashCommandNewDescription' },
    { usage: '/compact', descriptionKey: 'input.slashCommandCompactDescription' },
    { usage: '/btw <message>', descriptionKey: 'input.slashCommandBtwDescription' },
  ];
  const renderedLines = commandLines.map((item) => (
    `- \`${item.usage}\`: ${t(item.descriptionKey)}`
  ));
  return `### ${t('input.slashHelpTitle')}\n\n${renderedLines.join('\n')}`;
}
