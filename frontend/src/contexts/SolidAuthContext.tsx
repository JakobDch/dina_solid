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
  isLoading: boolean;
  login: (issuer: string) => Promise<void>;
  logout: () => Promise<void>;
  fetch: typeof fetch;
  getAccessToken: () => Promise<string | undefined>;
}

const SolidAuthContext = createContext<SolidAuthContextType | undefined>(undefined);

interface SolidAuthProviderProps {
  children: ReactNode;
}

export const SolidAuthProvider: React.FC<SolidAuthProviderProps> = ({ children }) => {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [webId, setWebId] = useState<string | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize session on mount (handle redirect callback)
  useEffect(() => {
    const initSession = async () => {
      setIsLoading(true);
      try {
        await restoreSession();
        setIsLoggedIn(session.info.isLoggedIn);
        setWebId(session.info.webId);

        if (session.info.isLoggedIn) {
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
    };

    const handleSessionRestore = () => {
      setIsLoggedIn(session.info.isLoggedIn);
      setWebId(session.info.webId);
      if (session.info.isLoggedIn) {
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
  }, []);

  const login = useCallback(async (issuer: string) => {
    await solidLogin(issuer);
  }, []);

  const logout = useCallback(async () => {
    await solidLogout();
    setIsLoggedIn(false);
    setWebId(undefined);
  }, []);

  const value: SolidAuthContextType = {
    isLoggedIn,
    webId,
    isLoading,
    login,
    logout,
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
