import React, { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import {
  session,
  restoreSession,
  solidLogin,
  solidLogout,
  authenticatedFetch,
  getAccessToken
} from '../solidSession';

// Define the type locally to avoid import issues
export interface SolidAuthContextType {
  isLoggedIn: boolean;
  webId: string | undefined;
  catalogId: number | null;
  catalogTitle: string | null;
  catalogUrl: string | null;
  isLoading: boolean;
  login: (issuer: string) => Promise<void>;
  logout: () => Promise<void>;
  selectCatalog: (id: number, title: string, url?: string) => void;
  clearCatalog: () => void;
  fetch: typeof fetch;
  getAccessToken: () => Promise<string | undefined>;
}

const SolidAuthContext = createContext<SolidAuthContextType | undefined>(undefined);

const CATALOG_STORAGE_KEY = 'dina_solid_catalog';

interface StoredCatalogInfo {
  catalogId: number;
  catalogTitle: string;
  catalogUrl?: string;
}

interface SolidAuthProviderProps {
  children: ReactNode;
}

export const SolidAuthProvider: React.FC<SolidAuthProviderProps> = ({ children }) => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [webId, setWebId] = useState<string | undefined>(undefined);
  const [catalogId, setCatalogId] = useState<number | null>(null);
  const [catalogTitle, setCatalogTitle] = useState<string | null>(null);
  const [catalogUrl, setCatalogUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load stored catalog info from sessionStorage
  const loadStoredCatalog = useCallback(() => {
    try {
      const stored = sessionStorage.getItem(CATALOG_STORAGE_KEY);
      if (stored) {
        const catalogInfo: StoredCatalogInfo = JSON.parse(stored);
        setCatalogId(catalogInfo.catalogId);
        setCatalogTitle(catalogInfo.catalogTitle);
        setCatalogUrl(catalogInfo.catalogUrl || null);
      }
    } catch (error) {
      console.error('Failed to load stored catalog info:', error);
    }
  }, []);

  // Save catalog info to sessionStorage
  const saveCatalogInfo = useCallback((id: number, title: string, url?: string) => {
    try {
      const catalogInfo: StoredCatalogInfo = { catalogId: id, catalogTitle: title, catalogUrl: url };
      sessionStorage.setItem(CATALOG_STORAGE_KEY, JSON.stringify(catalogInfo));
    } catch (error) {
      console.error('Failed to save catalog info:', error);
    }
  }, []);

  // Clear catalog info from sessionStorage
  const clearCatalogInfo = useCallback(() => {
    try {
      sessionStorage.removeItem(CATALOG_STORAGE_KEY);
    } catch (error) {
      console.error('Failed to clear catalog info:', error);
    }
  }, []);

  // Initialize session on mount (handle redirect callback)
  useEffect(() => {
    const initSession = async () => {
      setIsLoading(true);
      try {
        await restoreSession();
        setIsLoggedIn(session.info.isLoggedIn);
        setWebId(session.info.webId);

        // If logged in, try to restore catalog selection
        if (session.info.isLoggedIn) {
          loadStoredCatalog();
        }
      } catch (error) {
        console.error('Failed to initialize Solid session:', error);
      } finally {
        setIsLoading(false);
      }
    };
    initSession();

    // Subscribe to session events
    const handleLogin = () => {
      setIsLoggedIn(session.info.isLoggedIn);
      setWebId(session.info.webId);
    };

    const handleLogout = () => {
      setIsLoggedIn(false);
      setWebId(undefined);
      setCatalogId(null);
      setCatalogTitle(null);
      setCatalogUrl(null);
      clearCatalogInfo();
    };

    const handleSessionRestore = () => {
      setIsLoggedIn(session.info.isLoggedIn);
      setWebId(session.info.webId);
      if (session.info.isLoggedIn) {
        loadStoredCatalog();
      }
    };

    session.events.on("login", handleLogin);
    session.events.on("logout", handleLogout);
    session.events.on("sessionRestore", handleSessionRestore);

    return () => {
      session.events.off("login", handleLogin);
      session.events.off("logout", handleLogout);
      session.events.off("sessionRestore", handleSessionRestore);
    };
  }, [loadStoredCatalog, clearCatalogInfo]);

  const login = useCallback(async (issuer: string) => {
    await solidLogin(issuer);
  }, []);

  const logout = useCallback(async () => {
    await solidLogout();
    setIsLoggedIn(false);
    setWebId(undefined);
    setCatalogId(null);
    setCatalogTitle(null);
    setCatalogUrl(null);
    clearCatalogInfo();
  }, [clearCatalogInfo]);

  const selectCatalog = useCallback((id: number, title: string, url?: string) => {
    setCatalogId(id);
    setCatalogTitle(title);
    setCatalogUrl(url || null);
    saveCatalogInfo(id, title, url);
  }, [saveCatalogInfo]);

  const clearCatalog = useCallback(() => {
    setCatalogId(null);
    setCatalogTitle(null);
    setCatalogUrl(null);
    clearCatalogInfo();
  }, [clearCatalogInfo]);

  const value: SolidAuthContextType = {
    isLoggedIn,
    webId,
    catalogId,
    catalogTitle,
    catalogUrl,
    isLoading,
    login,
    logout,
    selectCatalog,
    clearCatalog,
    fetch: authenticatedFetch,
    getAccessToken,
  };

  return (
    <SolidAuthContext.Provider value={value}>
      {children}
    </SolidAuthContext.Provider>
  );
};

export const useSolidAuth = (): SolidAuthContextType => {
  const context = useContext(SolidAuthContext);
  if (context === undefined) {
    throw new Error('useSolidAuth must be used within a SolidAuthProvider');
  }
  return context;
};
