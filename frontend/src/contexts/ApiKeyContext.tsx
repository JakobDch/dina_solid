import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

/**
 * Holds the language model API keys the user supplies.
 *
 * Keys stay in this browser. They are kept in localStorage and sent with the
 * request that needs them, never stored on the server: a shared backend
 * holding everyone's keys in plain text is a liability, and per-user keys mean
 * one person's quota is not spent by another.
 */

export type KeyProvider = 'deepseek' | 'openai' | 'fireworks';

export const KEY_PROVIDERS: KeyProvider[] = ['deepseek', 'openai', 'fireworks'];

const STORAGE_KEY = 'dina_api_keys';

type ApiKeys = Partial<Record<KeyProvider, string>>;

interface ApiKeyContextValue {
  keys: ApiKeys;
  setKey: (provider: KeyProvider, value: string) => void;
  clearKey: (provider: KeyProvider) => void;
  clearAll: () => void;
  /** The key for a provider, or undefined when none is stored. */
  getKey: (provider: KeyProvider | undefined) => string | undefined;
  hasKey: (provider: KeyProvider) => boolean;
}

const ApiKeyContext = createContext<ApiKeyContextValue | undefined>(undefined);

function readStoredKeys(): ApiKeys {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === 'object' && parsed !== null ? parsed : {};
  } catch {
    // A corrupted entry should not stop the application from starting.
    return {};
  }
}

export function ApiKeyProvider({ children }: { children: React.ReactNode }) {
  const [keys, setKeys] = useState<ApiKeys>(readStoredKeys);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
    } catch (error) {
      console.error('Could not save the API keys:', error);
    }
  }, [keys]);

  const setKey = useCallback((provider: KeyProvider, value: string) => {
    const trimmed = value.trim();
    setKeys((previous) => {
      if (!trimmed) {
        const { [provider]: _removed, ...rest } = previous;
        return rest;
      }
      return { ...previous, [provider]: trimmed };
    });
  }, []);

  const clearKey = useCallback((provider: KeyProvider) => {
    setKeys((previous) => {
      const { [provider]: _removed, ...rest } = previous;
      return rest;
    });
  }, []);

  const clearAll = useCallback(() => setKeys({}), []);

  const getKey = useCallback(
    (provider: KeyProvider | undefined) => (provider ? keys[provider] : undefined),
    [keys],
  );

  const hasKey = useCallback((provider: KeyProvider) => Boolean(keys[provider]), [keys]);

  const value = useMemo(
    () => ({ keys, setKey, clearKey, clearAll, getKey, hasKey }),
    [keys, setKey, clearKey, clearAll, getKey, hasKey],
  );

  return <ApiKeyContext.Provider value={value}>{children}</ApiKeyContext.Provider>;
}

export function useApiKeys(): ApiKeyContextValue {
  const context = useContext(ApiKeyContext);
  if (!context) {
    throw new Error('useApiKeys must be used inside an ApiKeyProvider');
  }
  return context;
}
