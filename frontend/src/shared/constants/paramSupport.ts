/**
 * Shared parameter support mapping for LLM providers.
 * Maps parameter names to the list of SDK classes that support them.
 */
export const PARAM_SUPPORT: Record<string, string[]> = {
  max_tokens: ['openai', 'deepseek', 'anthropic', 'ollama', 'local_gguf', 'xai', 'kimi'],
  top_p: ['openai', 'deepseek', 'anthropic', 'ollama', 'local_gguf', 'xai', 'kimi'],
  top_k: ['anthropic', 'ollama', 'local_gguf'],
  frequency_penalty: ['openai', 'deepseek', 'local_gguf', 'xai', 'kimi'],
  presence_penalty: ['openai', 'deepseek', 'local_gguf', 'xai', 'kimi'],
};
