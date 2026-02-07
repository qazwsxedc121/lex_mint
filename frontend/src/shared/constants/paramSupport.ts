/**
 * Shared parameter support mapping for LLM providers.
 * Maps parameter names to the list of SDK classes that support them.
 */
export const PARAM_SUPPORT: Record<string, string[]> = {
  max_tokens: ['openai', 'deepseek', 'anthropic', 'ollama', 'xai'],
  top_p: ['openai', 'deepseek', 'anthropic', 'ollama', 'xai'],
  top_k: ['anthropic', 'ollama'],
  frequency_penalty: ['openai', 'deepseek', 'xai'],
  presence_penalty: ['openai', 'deepseek', 'xai'],
};
