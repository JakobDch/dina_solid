import { api } from '../api/apiClient';
import { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { ChatTab, TabManagerState, ChatMessage, SemanticModelEntry } from '../types';

// Filler words dropped when deriving a tab title from the question.
// Both languages are listed because the interface is bilingual and the
// question may be asked in either.
const STOPWORDS = [
  'wie', 'was', 'wann', 'wo', 'warum', 'der', 'die', 'das', 'und', 'oder',
  'ist', 'sind', 'ein', 'eine', 'einen', 'von', 'mit', 'fuer', 'auf', 'in',
  'how', 'what', 'when', 'where', 'why', 'the', 'and', 'or', 'is', 'are',
  'a', 'an', 'of', 'with', 'for', 'on', 'in', 'to',
];

export function useChatTabs(workspaceId?: string) {
  const { t } = useTranslation();

  const initialChatHistory = [
    {
      key: `llm-general-1-initial`,
      id: `llm-general-1-initial`,
      sender: 'llm',
      message: t('chat.greetingIntro'),
      timestamp: new Date().toISOString(),
      is_user_message: false,
    },
    {
      key: `llm-general-2-initial`,
      id: `llm-general-2-initial`,
      sender: 'llm',
      message: t('chat.greetingHelp'),
      timestamp: new Date().toISOString(),
      is_user_message: false,
    },
  ];

  const [tabState, setTabState] = useState<TabManagerState>({
    tabs: [{
      id: 'tab-1',
      title: 'Chat 1',
      isActive: true,
      hasSession: false,
      sessionId: undefined, // Explicitly no session
      initialQuery: undefined, // No initial query
      chatHistory: initialChatHistory,
      modelInfoBlocks: [],
      modelCheckHints: [],
      createdAt: new Date().toISOString(),
    }],
    activeTabId: 'tab-1',
    nextTabId: 2,
  });

  const createNewTab = useCallback(() => {
    // Creating new tab - this should start fresh but not affect other tabs

    setTabState(prev => {
      const newTabId = `tab-${prev.nextTabId}`;
      const newTab: ChatTab = {
        id: newTabId,
        title: `Chat ${prev.nextTabId}`,
        isActive: false,
        hasSession: false,
        sessionId: undefined, // Explicitly no session
        initialQuery: undefined, // No initial query
        chatHistory: [
          {
            key: `llm-general-1-${Date.now()}`,
            id: `llm-general-1-${Date.now()}`,
            sender: 'llm',
            message: t('chat.greetingStandardMode'),
            timestamp: new Date().toISOString(),
            is_user_message: false,
          },
          {
            key: `llm-general-2-${Date.now() + 1}`,
            id: `llm-general-2-${Date.now() + 1}`,
            sender: 'llm',
            message: t('chat.greetingStandardHelp'),
            timestamp: new Date().toISOString(),
            is_user_message: false,
          },
        ],
        modelInfoBlocks: [],
        modelCheckHints: [],
        createdAt: new Date().toISOString(),
      };

      // Switch to the new tab immediately but preserve other tabs' sessions
      return {
        tabs: prev.tabs.map(tab => ({ 
          ...tab, 
          isActive: false
        })).concat(newTab.id === newTabId ? { ...newTab, isActive: true } : newTab),
        activeTabId: newTabId,
        nextTabId: prev.nextTabId + 1,
      };
    });
  }, [workspaceId, t]);

  const switchToTab = useCallback((tabId: string) => {
    setTabState(prev => ({
      ...prev,
      tabs: prev.tabs.map(tab => ({
        ...tab,
        isActive: tab.id === tabId,
      })),
      activeTabId: tabId,
    }));
  }, []);

  const closeTab = useCallback(async (tabId: string) => {
    setTabState(prev => {
      // Don't allow closing the last tab
      if (prev.tabs.length <= 1) {
        return prev;
      }

      const tabToClose = prev.tabs.find(tab => tab.id === tabId);
      const newTabs = prev.tabs.filter(tab => tab.id !== tabId);
      
      // If closing the active tab, switch to the first remaining tab
      let newActiveTabId = prev.activeTabId;
      if (prev.activeTabId === tabId) {
        newActiveTabId = newTabs[0]?.id || null;
        // Update the isActive flag for the new active tab
        newTabs.forEach(tab => {
          tab.isActive = tab.id === newActiveTabId;
        });
      }

      // Clean up backend session if it exists
      if (tabToClose?.sessionId) {
        // Note: This would normally be an async operation, but we're handling it in the background
        fetch(`${api.defaults.baseURL}/api/v1/chat/sessions/${tabToClose.sessionId}`, {
          method: 'DELETE'
        }).catch(console.error);
      }

      return {
        tabs: newTabs,
        activeTabId: newActiveTabId,
        nextTabId: prev.nextTabId,
      };
    });
  }, []);

  const updateTabChatHistory = useCallback((tabId: string, historyOrUpdater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    setTabState(prev => {
      const currentTab = prev.tabs.find(t => t.id === tabId);
      if (!currentTab) return prev;
      
      let newHistory: ChatMessage[];
      
      if (typeof historyOrUpdater === 'function') {
        // Handle function updater
        newHistory = historyOrUpdater(currentTab.chatHistory);
      } else {
        // Handle direct array
        newHistory = historyOrUpdater;
      }
      
      // Simple length check to avoid unnecessary updates
      if (currentTab.chatHistory.length === newHistory.length && newHistory.length > 0) {
        // Check if the last message is the same
        const currentLast = currentTab.chatHistory[currentTab.chatHistory.length - 1];
        const newLast = newHistory[newHistory.length - 1];
        if (currentLast?.key === newLast?.key && currentLast?.message === newLast?.message) {
          return prev; // No change
        }
      }
      
      const updatedTabs = prev.tabs.map(tab =>
        tab.id === tabId
          ? { ...tab, chatHistory: [...newHistory] }
          : tab
      );
      
      return {
        ...prev,
        tabs: updatedTabs,
      };
    });
  }, []);

  const updateTabSession = useCallback((tabId: string, sessionId: string, initialQuery?: string) => {
    setTabState(prev => ({
      ...prev,
      tabs: prev.tabs.map(tab =>
        tab.id === tabId
          ? { 
              ...tab, 
              hasSession: true, 
              sessionId, 
              initialQuery: initialQuery || tab.initialQuery 
            }
          : tab
      ),
    }));
  }, []);

  // Helper function to generate a tab title based on model info blocks
  const generateTabTitle = useCallback((modelInfoBlocks: SemanticModelEntry[]): string => {
    if (!modelInfoBlocks || !Array.isArray(modelInfoBlocks) || modelInfoBlocks.length === 0) {
      return t('chat.tabGeneral');
    }

    // Check if we have a user query instead of filenames
    const firstEntry = modelInfoBlocks[0];
    if (firstEntry?.filename && !firstEntry.filename.includes('.') && firstEntry.filename.length > 10) {
      // This looks like a user query, not a filename

      // Extract meaningful keywords from the user query.
      // The stop word list below is German because user queries are typically
      // German; it filters query text, it is not displayed anywhere.
      const query = firstEntry.filename.toLowerCase();
      const words = query
        .split(/\s+/)
        .filter(word => word.length > 2)
        .filter(word => !STOPWORDS.includes(word));

      // Take first 2-3 meaningful words and create a title
      const titleWords = words.slice(0, 3);
      if (titleWords.length > 0) {
        const result = titleWords
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ');
        return result.length > 20 ? titleWords.slice(0, 2).map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ') : result;
      }
    }

    // Fallback: process as filenames

    const keywords = modelInfoBlocks
      .map(model => model.filename)
      .map(filename => filename.replace(/\.(ttl|rdf|owl|n3|jsonld)$/i, '').replace(/_(sm|semantic_model|transformed|rdf)$/i, '').replace(/^(semantic_|model_|sm_|00\d+_)/i, ''))
      .map(name => name.split(/[_\-]/).filter(word => word.length > 2 && !['semantic', 'model', 'transformed'].includes(word.toLowerCase())))
      .flat();

    if (keywords.length === 0) {
      return t('chat.tabDataAnalysis');
    }

    const result = keywords.slice(0, 2)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' & ');

    return result;
  }, [t]);

  const updateTabModelData = useCallback((
    tabId: string,
    modelInfoBlocks: SemanticModelEntry[],
    modelCheckHints: string[],
    extractedKeywords?: string[]
  ) => {
    setTabState(prev => {
      // Use backend keywords if available, otherwise fall back to generateTabTitle
      let newTitle: string;
      if (extractedKeywords && extractedKeywords.length > 0) {
        newTitle = extractedKeywords.slice(0, 3).map(keyword =>
          keyword.charAt(0).toUpperCase() + keyword.slice(1)
        ).join(' ');
      } else {
        newTitle = generateTabTitle(modelInfoBlocks);
      }

      return {
        ...prev,
        tabs: prev.tabs.map(tab =>
          tab.id === tabId
            ? {
                ...tab,
                modelInfoBlocks,
                modelCheckHints,
                title: newTitle
              }
            : tab
        ),
      };
    });
  }, [generateTabTitle]);

  const resetTabSession = useCallback((tabId: string) => {
    setTabState(prev => ({
      ...prev,
      tabs: prev.tabs.map(tab =>
        tab.id === tabId
          ? { 
              ...tab,
              hasSession: false,
              sessionId: undefined,
              initialQuery: undefined,
            }
          : tab
      ),
    }));
  }, []);

  const resetTabToInitialState = useCallback((tabId: string, pipelineMode: 'general' | 'esg_reporting' = 'general') => {
    setTabState(prev => ({
      ...prev,
      tabs: prev.tabs.map(tab =>
        tab.id === tabId
          ? {
              ...tab,
              hasSession: false,
              sessionId: undefined,
              initialQuery: undefined,
              chatHistory: pipelineMode === 'general' ? [
                {
                  key: `llm-general-1-${Date.now()}`,
                  id: `llm-general-1-${Date.now()}`,
                  sender: 'llm',
                  message: t('chat.greetingStandardMode'),
                  timestamp: new Date().toISOString(),
                  is_user_message: false,
                },
                {
                  key: `llm-general-2-${Date.now() + 1}`,
                  id: `llm-general-2-${Date.now() + 1}`,
                  sender: 'llm',
                  message: t('chat.greetingStandardHelp'),
                  timestamp: new Date().toISOString(),
                  is_user_message: false,
                },
              ] : [
                {
                  key: `llm-esg-1-${Date.now()}`,
                  id: `llm-esg-1-${Date.now()}`,
                  sender: 'llm',
                  message: t('chat.greetingEsgMode'),
                  timestamp: new Date().toISOString(),
                  is_user_message: false,
                },
                {
                  key: `llm-esg-2-${Date.now() + 1}`,
                  id: `llm-esg-2-${Date.now() + 1}`,
                  sender: 'llm',
                  message: t('chat.greetingEsgHelp'),
                  timestamp: new Date().toISOString(),
                  is_user_message: false,
                },
                {
                  key: `llm-esg-3-${Date.now() + 2}`,
                  id: `llm-esg-3-${Date.now() + 2}`,
                  sender: 'llm',
                  message: t('chat.greetingEsgExamples'),
                  timestamp: new Date().toISOString(),
                  is_user_message: false,
                },
              ],
              modelInfoBlocks: [],
              modelCheckHints: [],
            }
          : tab
      ),
    }));
  }, [t]);

  const updateTabTitle = useCallback((tabId: string, extractedKeywords: string[]) => {
    if (!extractedKeywords || extractedKeywords.length === 0) {
      return;
    }

    setTabState(prev => {
      const newTitle = extractedKeywords.slice(0, 3).map(keyword =>
        keyword.charAt(0).toUpperCase() + keyword.slice(1)
      ).join(' ');

      return {
        ...prev,
        tabs: prev.tabs.map(tab =>
          tab.id === tabId
            ? { ...tab, title: newTitle }
            : tab
        ),
      };
    });
  }, []);

  const getActiveTab = useCallback(() => {
    return tabState.tabs.find(tab => tab.id === tabState.activeTabId) || null;
  }, [tabState.tabs, tabState.activeTabId]);

  return {
    tabs: tabState.tabs,
    activeTabId: tabState.activeTabId,
    activeTab: getActiveTab(),
    createNewTab,
    switchToTab,
    closeTab,
    updateTabChatHistory,
    updateTabSession,
    updateTabModelData,
    updateTabTitle,
    resetTabSession,
    resetTabToInitialState,
  };
}