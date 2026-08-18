import type { KeyProvider } from '../contexts/ApiKeyContext';

/**
 * Which credential a model profile draws on.
 *
 * Mirrors get_profile_provider() in the backend: several profiles share one
 * provider, so the key is chosen by provider rather than by model.
 */
export function providerForProfile(profile: string): KeyProvider | undefined {
  if (profile.startsWith('fireworks')) return 'fireworks';
  if (profile.startsWith('deepseek')) return 'deepseek';
  if (profile.startsWith('openai')) return 'openai';
  // Ollama runs locally and needs no key.
  return undefined;
}
