import React, { createContext, useContext, useState, useEffect } from 'react';
import type { ChatSessionData, SemanticModelEntry } from '../types';
import { ChatStateManager } from '../utils/chatStateManager';
import { useParams } from 'react-router-dom';

interface ChatContextType {
  workspaceId: string | null;
  currentSession: ChatSessionData | null;
  currentModelInfoBlocks: SemanticModelEntry[];
  currentModelCheckHints: string[];
  showKIConfiguration: boolean;
  toggleKIConfiguration: () => void;
  saveSession: (session: ChatSessionData) => void;
  loadSession: () => ChatSessionData | null;
  clearSession: () => void;
  updateSession: (updates: Partial<ChatSessionData>) => void;
  setCurrentModelInfoBlocks: (blocks: SemanticModelEntry[]) => void;
  setCurrentModelCheckHints: (hints: string[]) => void;
  hasValidSession: boolean;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
  children: React.ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const { id } = useParams<{ id: string }>();
  const [currentSession, setCurrentSession] = useState<ChatSessionData | null>(null);
  const [currentModelInfoBlocks, setCurrentModelInfoBlocks] = useState<SemanticModelEntry[]>([]);
  const [currentModelCheckHints, setCurrentModelCheckHints] = useState<string[]>([]);
  const [hasValidSession, setHasValidSession] = useState(false);
  const [showKIConfiguration, setShowKIConfiguration] = useState<boolean>(false);

  // Clear any existing localStorage data on mount to ensure fresh start
  useEffect(() => {
    ChatStateManager.clearState();
    console.log('CHATCONTEXT: Cleared localStorage data for fresh start');
  }, []);

  const saveSession = (session: ChatSessionData) => {
    setCurrentSession(session);
    ChatStateManager.saveState(session);
    setHasValidSession(true);
  };

  const loadSession = (): ChatSessionData | null => {
    const session = ChatStateManager.loadState();
    setCurrentSession(session);
    setHasValidSession(session !== null);
    return session;
  };

  const clearSession = () => {
    setCurrentSession(null);
    ChatStateManager.clearState();
    setHasValidSession(false);
  };

  const updateSession = (updates: Partial<ChatSessionData>) => {
    if (currentSession) {
      const updatedSession = { ...currentSession, ...updates };
      setCurrentSession(updatedSession);
      ChatStateManager.saveSession(updatedSession);
    }
  };

  const toggleKIConfiguration = () => {
    setShowKIConfiguration(prev => !prev);
  };

  const value: ChatContextType = {
    workspaceId: id || null,
    currentSession,
    currentModelInfoBlocks,
    currentModelCheckHints,
    showKIConfiguration,
    toggleKIConfiguration,
    saveSession,
    loadSession,
    clearSession,
    updateSession,
    setCurrentModelInfoBlocks,
    setCurrentModelCheckHints,
    hasValidSession
  };

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChatContext = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};