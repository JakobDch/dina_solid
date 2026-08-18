import { useState, useRef, useEffect } from 'react';
import {
  Typography, Button, Space, Form, Switch,
  message
} from 'antd';
import type { MenuProps } from 'antd';
import { api } from '../../api/apiClient';
import type {
  ChatMessage,
  AgentResponseGroup,
  ReasoningStep,
  FinalResult,
  CurrentStepInfo
} from '../../types';
import { isReasoningOnlyStepId } from '../../types';
import { useTranslation } from 'react-i18next';
import { useChatContext } from '../../contexts/ChatContext';
import { useSolidAuth } from '../../contexts/SolidAuthContext';
import { useApiKeys } from '../../contexts/ApiKeyContext';
import { providerForProfile } from '../../utils/llmProviders';
import ApiKeySettingsModal from '../common/ApiKeySettingsModal';
import { useComunicaQuery } from '../../hooks/useComunicaQuery';
import type { ComunicaDatasetUrl } from '../../types';

// Import our new components
import ChatMessageList from './ChatMessageList';
import ChatInput from './ChatInput';
import SessionManager from './SessionManager';
import ModelSelector from './ModelSelector';
import ChatSidebar from './ChatSidebar';
import { useServerSentEvents, type EventHandlers } from '../../hooks/useServerSentEvents';
import { useChatTabs } from '../../hooks/useChatTabs';
import { useCallback } from 'react';
import { useParams } from 'react-router-dom';

export default function ChatInterface(): React.JSX.Element {
  // Get workspace ID directly from URL params (more reliable than context)
  const { id: workspaceId } = useParams<{ id: string }>();

  // Use the chat context
  const {
    setCurrentModelInfoBlocks,
    setCurrentModelCheckHints,
    showKIConfiguration,
    toggleKIConfiguration
  } = useChatContext();

  // Solid Pod authentication and external catalog
  const { t, i18n } = useTranslation();
  const { isLoggedIn: isSolidLoggedIn, catalogId, catalogUrl, getAccessToken } = useSolidAuth();
  const { getKey } = useApiKeys();
  const [serverProvidedKeys, setServerProvidedKeys] = useState<Record<string, boolean>>({});
  const [apiKeyPromptVisible, setApiKeyPromptVisible] = useState(false);

  // Some deployments configure a key in the environment; in that case the user
  // does not have to supply one.
  useEffect(() => {
    api
      .get<{ configured_on_server: Record<string, boolean> }>('/api/v1/agent/profiles')
      .then((response) => setServerProvidedKeys(response.data.configured_on_server ?? {}))
      .catch(() => setServerProvidedKeys({}));
  }, []);
  const { executeQuery: executeComunicaQuery } = useComunicaQuery();

  // Additional UI state for Retrieval settings

  // Tab management
  const {
    tabs,
    activeTabId,
    activeTab,
    createNewTab,
    switchToTab,
    closeTab,
    updateTabChatHistory,
    updateTabSession,
    updateTabModelData,
    updateTabTitle,
  } = useChatTabs(workspaceId || undefined);

  // Use tab-specific chat history instead of local state
  const chatHistory = activeTab?.chatHistory || [];
  const modelCheckHints = activeTab?.modelCheckHints || [];
  const isFollowUpMode = activeTab?.hasSession && !!activeTab?.sessionId;

  // Chat state
  const [chatInput, setChatInput] = useState<string>('');
  
  // LLM configuration
  const [selectedLLMProfile, setSelectedLLMProfile] = useState<string>('deepseek_chat');
  const [internalReasoningEnabled, setInternalReasoningEnabled] = useState<boolean>(false);
  const [fewShotPromptingEnabled, setFewShotPromptingEnabled] = useState<boolean>(true);
  const [agenticReasoningEnabled, setAgenticReasoningEnabled] = useState<boolean>(false);
  const [isChatLoading, setIsChatLoading] = useState<boolean>(false);
  
  // Pipeline mode state
  const [pipelineMode] = useState<'general' | 'esg_reporting'>('general');

  // Agent mode state - when enabled, uses the orchestrating agent endpoint
  const [useAgentMode, setUseAgentMode] = useState<boolean>(true);
  
  // Interactive mode state
  const [interactiveMode, setInteractiveMode] = useState<boolean>(false);

  // Auto-execute plans state (default: true = plans execute immediately)
  const [autoExecutePlans, setAutoExecutePlans] = useState<boolean>(true);

  // Plan confirmation state (when autoExecutePlans is false)
  const [isWaitingForPlanConfirmation, setIsWaitingForPlanConfirmation] = useState<boolean>(false);
  const [pendingPlan, setPendingPlan] = useState<any>(null);

  // User input for agent error state
  const [isWaitingForUserInput, setIsWaitingForUserInput] = useState<boolean>(false);
  const [userInputContext, setUserInputContext] = useState<any>(null);

  // Clarification state
  const [isWaitingForClarification, setIsWaitingForClarification] = useState<boolean>(false);
  const [clarificationContext, setClarificationContext] = useState<any>(null);

  // Agent clarification state (when agent plan is paused for user answer)
  const [isWaitingForAgentClarification, setIsWaitingForAgentClarification] = useState<boolean>(false);
  const [agentClarificationContext, setAgentClarificationContext] = useState<any>(null);

  // Model selection state
  const [isWaitingForModelSelection, setIsWaitingForModelSelection] = useState<boolean>(false);
  const [modelSelectionContext, setModelSelectionContext] = useState<any>(null);
  const [selectedModelsForConfirmation, setSelectedModelsForConfirmation] = useState<string[]>([]);
  
  // Chat Session state
  const [activeSession, setActiveSession] = useState<any>(null);
  const [currentUserQuery, setCurrentUserQuery] = useState<string>("");
  
  // Streaming state
  // streamingMessages removed - was unused after refactoring
  const [activeStreamIds, setActiveStreamIds] = useState<Set<string>>(new Set());
  
  // Export state
  const [exportingQuery, setExportingQuery] = useState<string | null>(null);

  // Response Group State for ChatGPT-style reasoning display
  const [activeResponseGroup, setActiveResponseGroup] = useState<AgentResponseGroup | null>(null);
  const [responseGroups, setResponseGroups] = useState<Map<string, AgentResponseGroup>>(new Map());
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());
  const reasoningStepCounterRef = useRef<number>(0);

  // Calculate if results have been displayed based on chat history
  const hasResultsDisplayed = chatHistory.some(msg =>
    msg.sparql_results && msg.sparql_results.length >= 0 && msg.sparql_variables
  );

  // Debug: Log the initial state
  useEffect(() => {
    console.log('APP_START_DEBUG:', {
      activeTabId,
      activeTabHasSession: activeTab?.hasSession,
      activeTabSessionId: activeTab?.sessionId,
      isFollowUpMode,
      activeSessionExists: !!activeSession
    });
  }, [activeTabId, activeTab?.hasSession, activeTab?.sessionId, isFollowUpMode, activeSession]);

  
  // Refs
  const querySuccessfullyProcessedRef = useRef(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  
  // SSE Hook
  const { connectToEventStream } = useServerSentEvents();

  // Tab handlers
  const handleTabClick = useCallback((tabId: string) => {
    switchToTab(tabId);
  }, [switchToTab]);

  const handleTabClose = useCallback((tabId: string) => {
    closeTab(tabId);
  }, [closeTab]);

  const handleNewTab = useCallback(() => {
    createNewTab();
  }, [createNewTab]);

  // Update chat history handler to work with tabs
  const handleChatHistoryChange = useCallback((historyOrUpdater: any[] | ((prev: any[]) => any[])) => {
    if (!activeTabId) return;
    updateTabChatHistory(activeTabId, historyOrUpdater);
  }, [activeTabId, updateTabChatHistory]);

  // Update model data handler to work with tabs
  const handleModelDataChange = useCallback((blocks: any, hints: any, keywords?: string[]) => {
    if (activeTabId) {
      // Ensure blocks and hints are valid arrays
      const safeBlocks = Array.isArray(blocks) ? blocks : [];
      const safeHints = Array.isArray(hints) ? hints : [];

      updateTabModelData(activeTabId, safeBlocks, safeHints, keywords);
      // Also update the parent components if needed
      setCurrentModelInfoBlocks(safeBlocks);
      setCurrentModelCheckHints(safeHints);
    }
  }, [activeTabId, updateTabModelData, setCurrentModelInfoBlocks, setCurrentModelCheckHints]);

  // Update session creation handler to work with tabs
  const handleSessionCreate = useCallback((sessionId: string, initialQuery: string) => {
    if (activeTabId) {
      updateTabSession(activeTabId, sessionId, initialQuery);
    }
  }, [activeTabId, updateTabSession]);

  // ==========================================
  // Response Group Helper Functions (ChatGPT-style reasoning)
  // ==========================================

  const createResponseGroup = useCallback((userMessageKey: string): AgentResponseGroup => {
    reasoningStepCounterRef.current = 0;
    return {
      groupId: `group-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      userQueryKey: userMessageKey,
      startedAt: new Date().toISOString(),
      status: 'processing',
      reasoningSteps: [],
      finalResults: [],
    };
  }, []);

  const updateCurrentStep = useCallback((stepInfo: Partial<CurrentStepInfo>) => {
    setActiveResponseGroup(prev => {
      if (!prev) return null;
      return {
        ...prev,
        currentStep: {
          stepNumber: stepInfo.stepNumber ?? prev.currentStep?.stepNumber ?? 1,
          totalSteps: stepInfo.totalSteps ?? prev.currentStep?.totalSteps ?? 1,
          description: stepInfo.description ?? prev.currentStep?.description ?? 'Verarbeite...',
          intent: stepInfo.intent ?? prev.currentStep?.intent,
        }
      };
    });
  }, []);

  const addReasoningStep = useCallback((step: Omit<ReasoningStep, 'id' | 'stepNumber'>) => {
    setActiveResponseGroup(prev => {
      if (!prev) return null;
      reasoningStepCounterRef.current += 1;
      const newStep: ReasoningStep = {
        ...step,
        id: `step-${Date.now()}-${reasoningStepCounterRef.current}`,
        stepNumber: reasoningStepCounterRef.current,
      };
      return {
        ...prev,
        reasoningSteps: [...prev.reasoningSteps, newStep],
      };
    });
  }, []);

  // Mark the last reasoning step as completed
  const completeLastReasoningStep = useCallback(() => {
    setActiveResponseGroup(prev => {
      if (!prev || prev.reasoningSteps.length === 0) return prev;
      const lastIndex = prev.reasoningSteps.length - 1;
      const updatedSteps = [...prev.reasoningSteps];
      if (updatedSteps[lastIndex].status === 'running') {
        updatedSteps[lastIndex] = { ...updatedSteps[lastIndex], status: 'completed' };
      }
      return {
        ...prev,
        reasoningSteps: updatedSteps,
      };
    });
  }, []);

  const addFinalResult = useCallback((result: FinalResult) => {
    setActiveResponseGroup(prev => {
      if (!prev) return null;
      return {
        ...prev,
        finalResults: [...prev.finalResults, result],
      };
    });
  }, []);

  const completeResponseGroup = useCallback((status: 'completed' | 'error' = 'completed') => {
    setActiveResponseGroup(prev => {
      if (prev) {
        const completed: AgentResponseGroup = {
          ...prev,
          status,
          completedAt: new Date().toISOString(),
          currentStep: undefined,
        };
        setResponseGroups(groups => new Map(groups).set(completed.groupId, completed));
      }
      return null;
    });
  }, []);

  const toggleGroupExpansion = useCallback((groupId: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  }, []);

  // Check if a step_id produces a final result (inverse of isReasoningOnlyStepId)
  const isFinalResultStep = useCallback((stepId: string | undefined): boolean => {
    if (!stepId) return false;
    // A step produces a final result if it's NOT reasoning-only
    return !isReasoningOnlyStepId(stepId);
  }, []);

  // Model Selection Handlers
  const handleModelSelection = (selectedModels: string[]) => {
    setSelectedModelsForConfirmation(selectedModels);
  };

  const handleConfirmModels = async () => {
    if (!modelSelectionContext || selectedModelsForConfirmation.length === 0) {
      return;
    }

    setIsChatLoading(true);
    
    try {
      const response = await api.post('/api/v1/chat/confirm-models', {
        selected_models: selectedModelsForConfirmation,
        continue_pipeline: true,
        query_context: modelSelectionContext.query_context,
        llm_profile: selectedLLMProfile,
        agentic_reasoning_enabled: agenticReasoningEnabled,
        internal_reasoning_enabled: internalReasoningEnabled,
        few_shot_prompting_enabled: fewShotPromptingEnabled
      });

      const result = response.data;
      
      if (result.status === 'success') {
        // Add successful result to chat history
        const resultMessage: ChatMessage = {
          key: `result-${Date.now()}`,
          id: `result-${Date.now()}`,
          sender: 'llm',
          message: `${t('chat.queryRan')} ${result.selected_models?.join(', ') ?? ''}`,
          timestamp: new Date().toISOString(),
          is_user_message: false,
          sparql_query: result.generated_sparql_query,
          sparql_results: result.sparql_results
        };
        
        handleChatHistoryChange(prev => [...prev, resultMessage]);
        
      } else {
        // Handle error
        const errorMessage: ChatMessage = {
          key: `error-${Date.now()}`,
          id: `error-${Date.now()}`,
          sender: 'llm',
          message: `**Fehler:** ${result.error || 'Unbekannter Fehler bei der SPARQL-Generierung'}`,
          timestamp: new Date().toISOString(),
          is_user_message: false
        };
        
        handleChatHistoryChange(prev => [...prev, errorMessage]);
      }

    } catch (error: any) {
      console.error('Error confirming models:', error);
      
      const errorMessage: ChatMessage = {
        key: `error-${Date.now()}`,
        id: `error-${Date.now()}`,
        sender: 'llm',
        message: `${t('chat.modelConfirmFailed')}: ${error.message || t('chat.unknownError')}`,
        timestamp: new Date().toISOString(),
        is_user_message: false
      };
      
      handleChatHistoryChange(prev => [...prev, errorMessage]);
    } finally {
      setIsChatLoading(false);
      setIsWaitingForModelSelection(false);
      setModelSelectionContext(null);
      setSelectedModelsForConfirmation([]);
    }
  };

  const handleCancelModelSelection = () => {
    setIsWaitingForModelSelection(false);
    setModelSelectionContext(null);
    setSelectedModelsForConfirmation([]);
    setIsChatLoading(false);
  };

  // Plan confirmation handlers
  const handleConfirmPlan = async () => {
    if (!pendingPlan?.plan_id) {
      console.error('No pending plan to confirm');
      return;
    }

    setIsWaitingForPlanConfirmation(false);
    setIsChatLoading(true);

    // Add confirmation message to chat
    const confirmMessage: ChatMessage = {
      key: `plan-confirmed-${Date.now()}`,
      id: `plan-confirmed-${Date.now()}`,
      sender: 'user',
      message: t('chat.planConfirmed'),
      timestamp: new Date().toISOString(),
      is_user_message: true
    };
    handleChatHistoryChange(prev => [...prev, confirmMessage]);

    // Build params for plan confirmation endpoint
    const params = new URLSearchParams({
      plan_id: pendingPlan.plan_id,
      user_for_data: workspaceId || '',
      llm_profile: selectedLLMProfile,
      agentic_reasoning_enabled: agenticReasoningEnabled.toString(),
      internal_reasoning_enabled: internalReasoningEnabled.toString(),
      few_shot_prompting_enabled: fewShotPromptingEnabled.toString(),
      interactive_mode: interactiveMode.toString(),
    });

    if (activeTab?.sessionId) {
      params.append('session_id', activeTab.sessionId);
    }

    const sseConfig = {
      url: `${api.defaults.baseURL}/api/v1/agent/confirm-plan?${params.toString()}`,
      heartbeatTimeout: 120000
    };

    setPendingPlan(null);
    connectToEventStream(
      sseConfig,
      createPipelineEventHandlers(),
      querySuccessfullyProcessedRef
    );
  };

  const handleCancelPlan = async () => {
    if (!pendingPlan?.plan_id) {
      setIsWaitingForPlanConfirmation(false);
      setPendingPlan(null);
      return;
    }

    try {
      await fetch(`${api.defaults.baseURL}/api/v1/agent/cancel-plan?plan_id=${pendingPlan.plan_id}`, {
        method: 'POST'
      });
    } catch (error) {
      console.error('Error cancelling plan:', error);
    }

    // Add cancellation message to chat
    const cancelMessage: ChatMessage = {
      key: `plan-cancelled-${Date.now()}`,
      id: `plan-cancelled-${Date.now()}`,
      sender: 'user',
      message: '❌ Plan abgebrochen',
      timestamp: new Date().toISOString(),
      is_user_message: true
    };
    handleChatHistoryChange(prev => [...prev, cancelMessage]);

    setIsWaitingForPlanConfirmation(false);
    setPendingPlan(null);
    setIsChatLoading(false);
  };

  // Auto-scroll to bottom when chat history changes OR when loading state changes
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatHistory, isChatLoading, activeStreamIds]);

  // Sync activeSession with the active tab's session
  useEffect(() => {
    if (activeTab?.sessionId && activeSession?.id !== activeTab.sessionId) {
      // Tab has a session, but global activeSession doesn't match - create minimal session object
      setActiveSession({
        id: activeTab.sessionId,
        initial_query: activeTab.initialQuery || "Session restored",
        workspace_id: workspaceId
      });
    } else if (!activeTab?.sessionId && activeSession) {
      // Tab has no session, but global activeSession exists - clear it
      setActiveSession(null);
    }
  }, [activeTab?.sessionId, activeTab?.hasSession, activeSession?.id, activeTab?.initialQuery, workspaceId]);

  // DISABLED: Session auto-loading removed completely
  // Sessions are now managed per-tab through the tab management system


  // Session management functions
  const handleCreateSession = async (sparqlResults: any[], queryContext: any) => {
    try {
      console.log('FRONTEND DEBUG: handleCreateSession called');
      console.log('[Session] Creating session with SPARQL data:');
      console.log('  - sparql_query exists:', !!queryContext.sparql_query);
      console.log('  - sparql_results:', queryContext.sparql_results ?
        (Array.isArray(queryContext.sparql_results) ? `Array[${queryContext.sparql_results.length}]` : typeof queryContext.sparql_results) : 'null');
      console.log('  - sparql_variables:', queryContext.sparql_variables);

      if (true) { // Always create session when called
        const sessionData = {
          workspace_id: workspaceId,
          initial_query: queryContext.user_query || "Initial query",
          selected_models: queryContext.selected_models || [],
          model_info_blocks: queryContext.model_info_blocks || "",
          model_check_hints: queryContext.model_check_hints || "",
          // Include SPARQL data for agent visualization
          sparql_query: queryContext.sparql_query || null,
          sparql_results: queryContext.sparql_results || null,
          sparql_variables: queryContext.sparql_variables || null
        };
        console.log('[Session] Final sessionData being sent:', {
          ...sessionData,
          sparql_results: sessionData.sparql_results ?
            (Array.isArray(sessionData.sparql_results) ? `Array[${sessionData.sparql_results.length}]` : 'object') : null
        });

        const response = await fetch(`${api.defaults.baseURL}/api/v1/chat/sessions`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(sessionData),
        });
        
        if (response.ok) {
          const session = await response.json();
          setActiveSession(session);
          // Update the active tab to reflect the session
          if (activeTabId) {
            updateTabSession(activeTabId, session.id, queryContext.user_query || "Initial query");
          }
          console.log('Session created:', session.id);

          // Update tab title with selected models from session creation
          if (queryContext.selected_models?.length > 0) {
            // Pass extracted keywords directly to tab management
            const keywords = queryContext.extracted_keywords && Array.isArray(queryContext.extracted_keywords) && queryContext.extracted_keywords.length > 0
              ? queryContext.extracted_keywords
              : undefined;
            handleModelDataChange(queryContext.selected_models.map((filename: string) => ({ filename })), modelCheckHints, keywords);
          } else if (queryContext.model_info_blocks) {

            // Use extracted keywords if available, otherwise fallback to user query
            let tabName = 'Anfrage';
            const keywords = queryContext.extracted_keywords && Array.isArray(queryContext.extracted_keywords) && queryContext.extracted_keywords.length > 0
              ? queryContext.extracted_keywords
              : undefined;

            if (!keywords) {
              // Fallback to user query only if no keywords available
              let userQuery = queryContext.user_query;
              if (!userQuery || userQuery === 'Initial query') {
                const recentUserMsg = chatHistory.slice().reverse().find(msg => msg.is_user_message && msg.message.trim().length > 5);
                userQuery = recentUserMsg?.message || 'Anfrage';
              }
              tabName = userQuery;
            }

            // Use extracted keywords or user query for meaningful tab naming
            handleModelDataChange([{ filename: tabName }], modelCheckHints, keywords);
          } else {
          }

          const sessionMessage: ChatMessage = {
            key: `session-created-${Date.now()}`,
            id: `session-created-${Date.now()}`,
            sender: 'System',
            message: sparqlResults.length > 0 
              ? t('chat.sessionStartedData')
              : t('chat.sessionStartedQuery'),
            timestamp: new Date().toISOString(),
            is_user_message: false,
          };
          handleChatHistoryChange(prev => [...prev, sessionMessage]);
        }
      }
    } catch (error) {
      console.error('Error creating session:', error);
    }
  };


  // Handle agent clarification response - resume paused plan
  const handleAgentClarificationResponse = (userResponse: string) => {
    if (!agentClarificationContext) {
      console.error('No agent clarification context available');
      return;
    }

    setIsChatLoading(true);

    const params = new URLSearchParams({
      plan_id: agentClarificationContext.plan_id,
      user_response: userResponse,
      user_for_data: agentClarificationContext.workspace_id,
      llm_profile: agentClarificationContext.llm_profile,
      session_id: agentClarificationContext.session_id || '',
      agentic_reasoning_enabled: agentClarificationContext.agentic_reasoning_enabled.toString(),
      internal_reasoning_enabled: agentClarificationContext.internal_reasoning_enabled.toString(),
      few_shot_prompting_enabled: agentClarificationContext.few_shot_prompting_enabled.toString(),
      interactive_mode: agentClarificationContext.interactive_mode.toString()
    });

    const sseConfig = {
      url: `${api.defaults.baseURL}/api/v1/agent/continue-after-clarification?${params.toString()}`,
      heartbeatTimeout: 120000
    };

    // Note: We create handlers inline here since createPipelineEventHandlers is defined after this function
    const agentClarificationHandlers: EventHandlers = {
      onPipelineUpdate: (serverMessageData) => {
        const stepId = serverMessageData.step_id;
        // Filter reasoning-only steps (use same filter as main handler)
        if (isReasoningOnlyStepId(stepId)) {
          addReasoningStep({
            intent: stepId || 'unknown',
            description: 'Pipeline-Info',
            status: 'completed',
            details: serverMessageData.message,
          });
          return;
        }

        const pipelineMessage: ChatMessage = {
          key: `pipeline-${Date.now()}-${Math.random()}`,
          id: `pipeline-${Date.now()}-${Math.random()}`,
          sender: 'Pipeline-Info',
          message: serverMessageData.message,
          timestamp: new Date().toISOString(),
          is_user_message: false,
          step_id: stepId
        };
        handleChatHistoryChange(prev => [...prev, pipelineMessage]);
      },
      onMessageStreamStart: (data) => {
        // Filter reasoning-only steps
        if (isReasoningOnlyStepId(data.step_id)) {
          addReasoningStep({
            intent: data.step_id || 'streaming',
            description: data.sender || 'dina',
            status: 'running',
            details: data.message,
          });
          return;
        }
        const streamingMessage: ChatMessage = {
          key: data.id,
          id: data.id,
          sender: data.sender,
          message: data.message,
          timestamp: data.timestamp,
          is_user_message: false,
          request_timestamp: data.request_timestamp,
          step_id: data.step_id,
          is_streaming: true
        };
        setActiveStreamIds(prev => new Set(prev.add(data.id)));
        handleChatHistoryChange(prev => [...prev, streamingMessage]);
      },
      onMessageStreamChunk: (data) => {
        if (isReasoningOnlyStepId(data.step_id)) return;
        handleChatHistoryChange(prev =>
          prev.map(msg => msg.id === data.id ? { ...msg, message: data.message } : msg)
        );
      },
      onMessageStreamEnd: (data) => {
        if (isReasoningOnlyStepId(data.step_id)) {
          // Mark the last reasoning step as completed
          completeLastReasoningStep();
          return;
        }
        setActiveStreamIds(prev => {
          const updated = new Set(prev);
          updated.delete(data.id);
          return updated;
        });
        handleChatHistoryChange(prev =>
          prev.map(msg => msg.id === data.id ? { ...msg, message: data.message, is_streaming: false } : msg)
        );
      },
      onEndStream: () => {
        console.log('[Agent Clarification] Stream ended successfully - plan resumed.');
        setIsChatLoading(false);
        setIsWaitingForAgentClarification(false);
        setAgentClarificationContext(null);
      },
      onError: (error) => {
        console.error('Agent clarification EventSource failed:', error);
        setIsChatLoading(false);
        setIsWaitingForAgentClarification(false);
        setAgentClarificationContext(null);
        handleChatHistoryChange(prev => [...prev, {
          key: `error-agent-clarification-${Date.now()}`,
          id: `error-agent-clarification-${Date.now()}`,
          sender: 'System',
          message: 'Verbindung bei der Fortsetzung des Plans fehlgeschlagen.',
          timestamp: new Date().toISOString(),
          is_user_message: false,
        }]);
      },
      onAgentClarificationRequired: (data) => {
        console.log('[Agent Clarification] Plan paused again for another clarification:', data);
        setIsChatLoading(false);
        setIsWaitingForAgentClarification(true);
        setAgentClarificationContext({
          plan_id: data.plan_id,
          paused_step: data.paused_step,
          clarification_data: data.clarification_data,
          workspace_id: workspaceId,
          session_id: activeSession?.id,
          llm_profile: selectedLLMProfile,
          agentic_reasoning_enabled: agenticReasoningEnabled,
          internal_reasoning_enabled: internalReasoningEnabled,
          few_shot_prompting_enabled: fewShotPromptingEnabled,
          interactive_mode: interactiveMode,
        });
        message.info(t('chat.assistantAsksAgain'));
      },
      onClarificationRequired: (parsedData) => {
        // Handle nested clarification within agent flow
        if (parsedData.step_id === "clarification_metadata") {
          setIsWaitingForAgentClarification(true);
          message.info(t('chat.assistantAsks'));
        }
      }
    };

    connectToEventStream(sseConfig, agentClarificationHandlers);
  };

  // Event handlers
  const createPipelineEventHandlers = (): EventHandlers => ({
    onPipelineUpdate: (serverMessageData) => {
      let displayMessage = serverMessageData.message;
      let messageSender = "Pipeline-Info";
      const stepId = serverMessageData.step_id;

      // Handle plan created event - show detailed plan
      if (stepId === "agent_plan_created" && serverMessageData.plan?.steps) {
        const planSteps = serverMessageData.plan.steps;
        messageSender = "dina";
        displayMessage = `**Plan erstellt** (${planSteps.length} Schritt${planSteps.length > 1 ? 'e' : ''}):\n\n${planSteps.map((step: any) =>
          `${step.step_number}. **${step.intent}**: ${step.sub_query}${step.condition && step.condition !== 'always' ? ` _(${step.condition})_` : ''}`
        ).join('\n')}`;
      }


      // Hide the intermediate validation steps from the visible chat.
      const suppressedSteps = [
        "model_validation_success",           // redundancy check done
        "model_validation_fallback",         // Fallback-Validierung
        "incremental_validation_eliminated_all", // Alle Modelle eliminiert
        "interactive_model_selection",       // interactive choice, before confirmation
        "interactive_model_selection_after_clarification" // after a clarification
      ];

      if (suppressedSteps.includes(stepId)) {
        console.log(`[SUPPRESSED] Skipping display of step: ${stepId}`);
        return; // SKIP: Nicht im Chat anzeigen
      }

      // Update loading indicator with current step description
      const stepDescription = i18n.exists(`steps.${stepId}`)
        ? t(`steps.${stepId}`)
        : serverMessageData.message || t('common.loading');
      updateCurrentStep({
        stepNumber: serverMessageData.step_number || 1,
        totalSteps: serverMessageData.total_steps || 1,
        description: stepDescription,
        intent: serverMessageData.intent,
      });

      // Logic to determine sender based on stepId
      if (stepId === "identify_keywords_success" && serverMessageData.identified_keywords?.length > 0) {
        messageSender = "Keyword-Extraktion";
        const keywordList = serverMessageData.identified_keywords.map((kw: string) => `- ${kw}`).join('\n');
        displayMessage = `Folgende Keywords wurden extrahiert:\n${keywordList}`;
      } else if (stepId === "retrieval_success_for_keyword" && serverMessageData.found_models?.length > 0) {
        messageSender = "Semantische Suche";
        displayMessage = `${t('chat.candidatesFound', { keyword: serverMessageData.keyword })}`;
      } else if (stepId === "confirmed_model_selection") {
        messageSender = "Modell-Selektion";
        displayMessage = serverMessageData.message || t('chat.modelsConfirmed');
        // Extract model names from the message
        const modelMatches = displayMessage.match(/Bestätigte Modelle: (.+)/);
        if (modelMatches) {
          const modelNames = modelMatches[1].split(', ').map((name: string) => name.trim());
          // Pass extracted keywords if available
          const keywords = serverMessageData.extracted_keywords || undefined;
          handleModelDataChange(modelNames.map((filename: string) => ({ filename })), modelCheckHints, keywords);
        }
      } else if (stepId === "validation_passed") {
        messageSender = "Modell-Validierung";
        displayMessage = `**Prüfungsergebnis:** GEEIGNET\n**Begründung:** ${serverMessageData.validation_reasoning}`;
      } else if (stepId === "sparql_query_generated" || stepId === "agentic_reasoning_query_corrected") {
        messageSender = stepId === "sparql_query_generated" ? "SPARQL Query" : "Korrigierte SPARQL Query";
        displayMessage = serverMessageData.sparql_query || serverMessageData.corrected_sparql_query;
      } else if (stepId === "sparql_query_metadata") {
        return;
      } else if (stepId === "sparql_execution_completed") {
        messageSender = "SPARQL Ergebnis";
        displayMessage = serverMessageData.message || t('chat.queryExecuted');
      } else if (stepId === "load_session_context") {
        messageSender = "Session Kontext";
        displayMessage = serverMessageData.message || "Session-Kontext wird geladen...";
      } else if (stepId === "check_follow_up_answerability") {
        messageSender = t('chat.requestCheck');
        displayMessage = serverMessageData.message || t('chat.checkingAnswerable');
      } else if (stepId === "follow_up_not_answerable") {
        messageSender = "Anfrage nicht beantwortbar";
        displayMessage = serverMessageData.message || "Diese Anfrage kann nicht beantwortet werden.";
      } else if (stepId === "follow_up_answerable") {
        messageSender = "Anfrage beantwortbar";
        displayMessage = serverMessageData.message || "Anfrage kann beantwortet werden.";
      } else if (stepId === "generate_contextual_sparql") {
        messageSender = "Kontextuelle SPARQL-Generierung";
        displayMessage = serverMessageData.message || "Generiere SPARQL-Query basierend auf Session-Kontext...";
      } else if (stepId === "follow_up_sparql_error") {
        messageSender = "SPARQL Fehler";
        displayMessage = serverMessageData.message || t('chat.queryExecutionFailed');
      } else if (stepId === "sparql_execution_completed_empty") {
        messageSender = "SPARQL Ergebnis (leer)";
        displayMessage = serverMessageData.message || "SPARQL-Query ergab keine Ergebnisse.";
      } else {
        displayMessage = serverMessageData.message || "Unbekannter Schritt";
      }

      // Add to Response Group (for ChatGPT-style reasoning display)
      const isReasoning = isReasoningOnlyStepId(stepId);
      const isFinal = isFinalResultStep(stepId);

      if (isReasoning) {
        // Add as reasoning step (hidden in collapsed section)
        addReasoningStep({
          intent: serverMessageData.intent || stepId || 'unknown',
          description: messageSender,
          status: 'completed',
          details: displayMessage,
          sparqlQuery: stepId === 'sparql_query_generated' ? (serverMessageData.sparql_query || displayMessage) : undefined,
        });
        // Don't add to chat history - only show in reasoning section
        return;
      }

      if (isFinal) {
        // Add as final result (always visible)
        if (stepId === 'sparql_execution_completed' || stepId === 'sparql_execution_completed_empty') {
          addFinalResult({
            type: 'sparql_results',
            data: {
              query: serverMessageData.sparql_query,
              variables: serverMessageData.sparql_variables,
              results: serverMessageData.sparql_results,
              message: displayMessage,
            },
            messageKey: serverMessageData.id || `result-${Date.now()}`,
          });
        }
      }

      const newServerMessage: ChatMessage = {
        key: serverMessageData.id || `server-${Date.now()}-${Math.random()}`,
        id: serverMessageData.id,
        sender: messageSender,
        message: displayMessage,
        timestamp: serverMessageData.timestamp || new Date().toISOString(),
        is_user_message: false,
        request_timestamp: serverMessageData.request_timestamp,
        step_id: serverMessageData.step_id,
        sparql_query: serverMessageData.step_id === "sparql_execution_completed" ? serverMessageData.sparql_query : undefined,
        sparql_variables: serverMessageData.step_id === "sparql_execution_completed" ? serverMessageData.sparql_variables : undefined,
        sparql_results: serverMessageData.step_id === "sparql_execution_completed" ? serverMessageData.sparql_results : undefined,
        // Add correction-related data for SPARQL execution completed messages
        // Use user_query directly from backend event if available
        user_query: (serverMessageData.step_id === "sparql_execution_completed" || serverMessageData.step_id === "sparql_execution_completed_empty") ?
          serverMessageData.user_query : undefined,
        model_info_blocks: serverMessageData.step_id === "sparql_execution_completed" ? serverMessageData.model_info_blocks : undefined,
        selected_models: serverMessageData.step_id === "sparql_execution_completed" ?
          (serverMessageData.selected_models || []) : undefined,
      };
      handleChatHistoryChange(prev => [...prev, newServerMessage]);

      // Create session after successful SPARQL execution (only for new queries)
      if (stepId === "sparql_execution_completed" && !isFollowUpMode) {
        const queryContext = {
          user_query: serverMessageData.user_query || currentUserQuery || "Initial query",
          selected_models: activeTab?.modelInfoBlocks?.map(model => model.filename) || [],
          model_info_blocks: serverMessageData.model_info_blocks || JSON.stringify(activeTab?.modelInfoBlocks) || "",
          model_check_hints: serverMessageData.model_check_hints || activeTab?.modelCheckHints?.join('\n') || "",
          extracted_keywords: serverMessageData.extracted_keywords || [],
          // SPARQL data for agent visualization
          sparql_query: serverMessageData.sparql_query || serverMessageData.final_query,
          sparql_results: serverMessageData.sparql_results,
          sparql_variables: serverMessageData.sparql_variables || []
        };

        // Update tab title immediately if keywords are available
        if (activeTabId && serverMessageData.extracted_keywords && serverMessageData.extracted_keywords.length > 0) {
          updateTabTitle(activeTabId, serverMessageData.extracted_keywords);
        }

        // Backend sends sparql_results as the bindings array directly (not nested)
        handleCreateSession(serverMessageData.sparql_results || [], queryContext);
      }
    },

    onClarificationRequired: (parsedData) => {
      // Only handle metadata events, not display messages (those are now streamed)
      if (parsedData.step_id === "clarification_metadata") {
        setClarificationContext({
          original_user_query: chatInput,
          user_response: '',
          llm_profile: selectedLLMProfile,
          validated_models_json: parsedData.validated_models_json,
          initial_llm_reasoning: parsedData.initial_reasoning,
          clarification_question: parsedData.clarification_question,
          workspace_id: workspaceId,
          agentic_reasoning_enabled: agenticReasoningEnabled,
          internal_reasoning_enabled: internalReasoningEnabled,
          few_shot_prompting_enabled: fewShotPromptingEnabled,
        });

        setIsWaitingForClarification(true);
        setIsChatLoading(false);
        message.info(t('chat.assistantAsks'));
      }
    },

    onMessageStreamStart: (data) => {
      // Check if this is a reasoning-only step - if so, don't show in chat
      if (isReasoningOnlyStepId(data.step_id)) {
        // Add to reasoning steps instead
        addReasoningStep({
          intent: data.step_id || 'streaming',
          description: data.sender || 'dina',
          status: 'running',
          details: data.message,
        });
        return;
      }

      const streamingMessage: ChatMessage = {
        key: data.id,
        id: data.id,
        sender: data.sender,
        message: data.message,
        timestamp: data.timestamp,
        is_user_message: false,
        request_timestamp: data.request_timestamp,
        step_id: data.step_id,
        is_streaming: true
      };

      setActiveStreamIds(prev => new Set(prev.add(data.id)));
      handleChatHistoryChange(prev => [...prev, streamingMessage]);
    },

    onMessageStreamChunk: (data) => {
      // Skip if this is a reasoning-only step
      if (isReasoningOnlyStepId(data.step_id)) {
        return;
      }
      handleChatHistoryChange(prev =>
        prev.map(msg =>
          msg.id === data.id
            ? { ...msg, message: data.message }
            : msg
        )
      );
    },

    onMessageStreamEnd: (data) => {
      // If reasoning-only step, mark as completed instead of skipping
      if (isReasoningOnlyStepId(data.step_id)) {
        completeLastReasoningStep();
        return;
      }
      setActiveStreamIds(prev => {
        const updated = new Set(prev);
        updated.delete(data.id);
        return updated;
      });

      handleChatHistoryChange(prev =>
        prev.map(msg =>
          msg.id === data.id
            ? { ...msg, message: data.message, is_streaming: false }
            : msg
        )
      );
    },

    onEndStream: (data) => {
      console.log('[Chat] Stream ended successfully by server.', data);
      querySuccessfullyProcessedRef.current = true;
      completeResponseGroup('completed');

      // Store session_id from server if received and no session exists yet
      if (data?.session_id && !activeTab?.sessionId) {
        console.log('[Chat] Storing new session_id from server:', data.session_id);
        handleSessionCreate(data.session_id, currentUserQuery || "Query");
      }

      if (!isWaitingForClarification) {
        setIsChatLoading(false);
      }
    },

    onError: (error) => {
      console.error('EventSource failed:', error);
      completeResponseGroup('error');
      setIsChatLoading(false);
      handleChatHistoryChange(prev => [...prev, {
        key: `error-eventsource-${Date.now()}`,
        id: `error-eventsource-${Date.now()}`,
        sender: 'System',
        message: 'Verbindung zum Server fehlgeschlagen oder Stream unterbrochen.',
        timestamp: new Date().toISOString(),
        is_user_message: false,
      }]);
    },

    // Agent-specific event handlers
    onCorpusInfo: (data) => {
      console.log('[Agent] Corpus info received:', data);
      // Add to response group as final result (displayed via AgentResponseContainer)
      // NOTE: We do NOT add to chatHistory here to avoid duplicate display
      addFinalResult({
        type: 'corpus_info',
        data: {
          files: data.corpus_files,
          totalFiles: data.total_files,
          message: data.message,
        },
        messageKey: `corpus-info-${Date.now()}`,
      });
    },

    onVisualizationResult: (data) => {
      console.log('[Agent] Visualization result received:', data);
      // Add to response group as final result (displayed via AgentResponseContainer)
      // NOTE: We do NOT add to chatHistory here to avoid duplicate display
      addFinalResult({
        type: 'visualization',
        data: {
          code: data.visualization_code,
          imageBase64: data.visualization_image_base64,
          message: data.message,
        },
        messageKey: `visualization-${Date.now()}`,
      });
    },

    onCalculationResult: (data) => {
      console.log('[Agent] Calculation result received:', data);
      // Add to response group as final result (displayed via AgentResponseContainer)
      // NOTE: We do NOT add to chatHistory here to avoid duplicate display
      addFinalResult({
        type: 'calculation',
        data: {
          code: data.calculation_code,
          summary: data.calculation_summary,
          table: data.calculation_table,
          metadata: data.calculation_metadata,
          json: data.calculation_json,
          message: data.message,
        },
        messageKey: `calculation-${Date.now()}`,
      });
    },

    onPipelineError: (data) => {
      console.log('[Agent] Pipeline error received:', data);
      setIsChatLoading(false);
      const errorMessage: ChatMessage = {
        key: `error-${Date.now()}`,
        id: `error-${Date.now()}`,
        sender: 'dina',
        message: data.message || 'Ein Fehler ist aufgetreten.',
        timestamp: new Date().toISOString(),
        is_user_message: false,
        step_id: data.step_id
      };
      handleChatHistoryChange(prev => [...prev, errorMessage]);
    },

    // Plan-based agent event handlers
    onPlanConfirmationRequired: (data) => {
      console.log('[Agent] Plan confirmation required:', data);
      setIsChatLoading(false);
      setIsWaitingForPlanConfirmation(true);
      setPendingPlan(data.plan);

      // Display the plan in chat for user to review
      const planSteps = data.plan?.steps || [];
      const planMessage: ChatMessage = {
        key: `plan-${Date.now()}`,
        id: `plan-${Date.now()}`,
        sender: 'dina',
        message: `**Geplante Schritte:**\n\n${planSteps.map((step: any, idx: number) =>
          `${idx + 1}. **${step.intent}**: ${step.sub_query}${step.condition && step.condition !== 'always' ? ` _(Bedingung: ${step.condition})_` : ''}`
        ).join('\n')}\n\n_Klicken Sie auf "Ausführen" um den Plan zu starten, oder "Abbrechen" um abzubrechen._`,
        timestamp: new Date().toISOString(),
        is_user_message: false,
        step_id: 'plan_confirmation_required'
      };
      handleChatHistoryChange(prev => [...prev, planMessage]);
    },

    onIntermediateMessage: (data) => {
      console.log('[Agent] Intermediate message:', data);
      const intermediateMsg: ChatMessage = {
        key: `intermediate-${Date.now()}-${Math.random()}`,
        id: `intermediate-${Date.now()}-${Math.random()}`,
        sender: 'dina',
        message: data.message,
        timestamp: new Date().toISOString(),
        is_user_message: false,
        step_id: data.step_id || 'intermediate_message'
      };
      handleChatHistoryChange(prev => [...prev, intermediateMsg]);
    },

    onPlanStepUpdate: (data) => {
      console.log('[Agent] Plan step update:', data);
      // Only show significant step updates (not every tiny progress)
      if (data.status === 'completed' || data.status === 'failed' || data.status === 'skipped') {
        const statusEmoji = data.status === 'completed' ? '✅' : data.status === 'failed' ? '❌' : '⏭️';
        const stepMessage: ChatMessage = {
          key: `step-${data.step_number}-${Date.now()}`,
          id: `step-${data.step_number}-${Date.now()}`,
          sender: 'Pipeline-Info',
          message: `${statusEmoji} Schritt ${data.step_number}: ${data.message || data.sub_query}`,
          timestamp: new Date().toISOString(),
          is_user_message: false,
          step_id: `plan_step_${data.step_number}_${data.status}`
        };
        handleChatHistoryChange(prev => [...prev, stepMessage]);
      }
    },

    onUserInputRequired: (data) => {
      console.log('[Agent] User input required:', data);
      setIsChatLoading(false);
      setIsWaitingForUserInput(true);
      setUserInputContext(data);

      // Display the request for help in chat
      const helpMessage: ChatMessage = {
        key: `user-input-${Date.now()}`,
        id: `user-input-${Date.now()}`,
        sender: 'dina',
        message: `${t('chat.needYourHelp')}

${data.message || t('chat.needMoreInfo')}`,
        timestamp: new Date().toISOString(),
        is_user_message: false,
        step_id: 'user_input_required'
      };
      handleChatHistoryChange(prev => [...prev, helpMessage]);
    },

    // Agent clarification required - plan is paused waiting for user answer
    onAgentClarificationRequired: (data) => {
      console.log('[Agent] Agent clarification required - plan paused:', data);
      setIsChatLoading(false);
      setIsWaitingForAgentClarification(true);

      // Store the context needed to resume the plan
      setAgentClarificationContext({
        plan_id: data.plan_id,
        paused_step: data.paused_step,
        clarification_data: data.clarification_data,
        workspace_id: workspaceId,
        session_id: activeSession?.id,
        llm_profile: selectedLLMProfile,
        agentic_reasoning_enabled: agenticReasoningEnabled,
        internal_reasoning_enabled: internalReasoningEnabled,
        few_shot_prompting_enabled: fewShotPromptingEnabled,
        interactive_mode: interactiveMode,
      });

      // Note: The clarification question is already shown via the normal user_clarification_required event
      // which is yielded before agent_clarification_required
      message.info(t('chat.assistantAsksResume'));
    },

    // Comunica execution required - agent is in Solid mode and wants frontend to execute via Comunica
    onComunicaExecutionRequired: async (data) => {
      console.log('[Agent Solid] Comunica execution required:', data);

      // Show status message
      const statusMessage: ChatMessage = {
        key: `comunica-status-${Date.now()}`,
        id: `comunica-status-${Date.now()}`,
        sender: 'Pipeline-Info',
        message: t('chat.runningOnCatalog', { count: data.dataset_urls?.length || 0 }),
        timestamp: new Date().toISOString(),
        is_user_message: false,
        step_id: 'comunica_execution_start'
      };
      handleChatHistoryChange(prev => [...prev, statusMessage]);

      try {
        // Execute the SPARQL query via Comunica
        const result = await executeComunicaQuery(
          data.sparql_query,
          data.dataset_urls.map((url: { url: string; title: string; identifier: string }) => ({
            url: url.url,
            title: url.title,
            identifier: url.identifier
          })) as ComunicaDatasetUrl[],
          (status: string) => {
            console.log('[Comunica] Status:', status);
          }
        );

        // Show results
        const resultMessage: ChatMessage = {
          key: `comunica-results-${Date.now()}`,
          id: `comunica-results-${Date.now()}`,
          sender: 'SPARQL Ergebnis',
          message: `Comunica Query abgeschlossen: ${result.total} Ergebnisse in ${(result.executionTime / 1000).toFixed(2)}s`,
          timestamp: new Date().toISOString(),
          is_user_message: false,
          sparql_results: result.results,
          sparql_variables: result.variables,
          sparql_query: data.sparql_query,
          step_id: 'comunica_execution_completed'
        };
        handleChatHistoryChange(prev => [...prev, resultMessage]);

        // Get the original user query from chat history (last user message)
        const lastUserMessage = chatHistory.filter(m => m.is_user_message).pop();
        const originalUserQuery = lastUserMessage?.message || 'Comunica Query';

        // Send results back to agent for context storage and plan continuation
        // Include all necessary data for session creation in Solid mode
        const comunicaSessionId = data.session_id || activeSession?.id || '';
        const response = await api.post('/api/v1/agent/comunica-results', {
          session_id: comunicaSessionId,
          step_number: data.step_number || 1,
          results: result.results,
          variables: result.variables,
          total: result.total,
          // NEW: Additional fields for session creation
          workspace_id: workspaceId,
          user_query: originalUserQuery,
          sparql_query: data.sparql_query,
          catalog_id: catalogId?.toString(),
          catalog_url: catalogUrl || ''
        });

        console.log('[Agent Solid] Comunica results sent to agent:', response.data);

        // CRITICAL: Save the session_id in the tab for follow-up queries
        if (comunicaSessionId && activeTabId && response.data.persisted) {
          console.log('[Agent Solid] Updating tab session with ID:', comunicaSessionId);
          updateTabSession(activeTabId, comunicaSessionId, originalUserQuery);
        }

        // If there are more steps, continue the plan
        if (response.data.has_more_steps) {
          console.log('[Agent Solid] Continuing plan execution...');

          const continueParams = new URLSearchParams({
            session_id: data.session_id || activeSession?.id || '',
            user_for_data: workspaceId || '',
            llm_profile: selectedLLMProfile,
            agentic_reasoning_enabled: agenticReasoningEnabled.toString(),
            internal_reasoning_enabled: internalReasoningEnabled.toString(),
            few_shot_prompting_enabled: fewShotPromptingEnabled.toString(),
            interactive_mode: interactiveMode.toString(),
          });

          const sseConfig = {
            url: `${api.defaults.baseURL}/api/v1/agent/continue-plan?${continueParams.toString()}`,
            heartbeatTimeout: 120000
          };

          connectToEventStream(
            sseConfig,
            createPipelineEventHandlers(),
            querySuccessfullyProcessedRef
          );
        } else {
          // No more steps, we're done
          setIsChatLoading(false);
        }

      } catch (error) {
        console.error('[Agent Solid] Comunica execution failed:', error);
        setIsChatLoading(false);

        const errorMessage: ChatMessage = {
          key: `comunica-error-${Date.now()}`,
          id: `comunica-error-${Date.now()}`,
          sender: 'System',
          message: `${t('chat.comunicaError')}: ${error instanceof Error ? error.message : t('chat.unknownError')}`,
          timestamp: new Date().toISOString(),
          is_user_message: false,
          step_id: 'comunica_execution_error'
        };
        handleChatHistoryChange(prev => [...prev, errorMessage]);
      }
    }
  });

  // Main chat submit handler
  const handleChatSubmit = async () => {
    if (!chatInput.trim() || isChatLoading) return;

    // Check if we're waiting for agent clarification response (plan paused)
    if (isWaitingForAgentClarification && agentClarificationContext) {
      const userResponseMessage: ChatMessage = {
        key: `user-agent-clarification-response-${Date.now()}`,
        sender: 'user',
        message: chatInput.trim(),
        timestamp: new Date().toISOString(),
        is_user_message: true,
      };
      handleChatHistoryChange(prev => [...prev, userResponseMessage]);
      handleAgentClarificationResponse(chatInput.trim());
      setChatInput('');
      return;
    }

    // Check if we're waiting for clarification response (non-agent pipeline)
    if (isWaitingForClarification) {
      const userResponseMessage: ChatMessage = {
        key: `user-clarification-response-${Date.now()}`,
        sender: 'user',
        message: chatInput.trim(),
        timestamp: new Date().toISOString(),
        is_user_message: true,
      };
      handleChatHistoryChange(prev => [...prev, userResponseMessage]);
      handleChatClarificationResponse(chatInput.trim());
      setChatInput('');
      return;
    }

    // Check if we're in follow-up mode - use tab data directly to avoid timing issues
    const shouldUseFollowUp = activeTab?.hasSession && !!activeTab?.sessionId;

    if (shouldUseFollowUp && activeTab?.sessionId) {
      handleFollowUpSubmit();
      return;
    }

    // Always use orchestrating agent for intelligent catalog-first routing
    handleAgentSubmit();
  };

  // Handle Comunica query execution (client-side SPARQL execution against Solid Pod data)
  // The stream cannot report a 400 body back to us, so check up front whether
  // the selected model has a key at all and point the user at the settings.
  const ensureApiKeyAvailable = (): boolean => {
    const provider = providerForProfile(selectedLLMProfile);
    if (!provider) return true; // Local model, no key needed.
    if (getKey(provider)) return true;
    if (serverProvidedKeys[provider]) return true;

    message.warning({
      content: t('apiKeys.missingBody', { provider }),
      duration: 6,
    });
    setApiKeyPromptVisible(true);
    return false;
  };

  // Hand the credentials the stream needs to the backend over a POST and keep
  // only the returned reference for the stream URL, so neither the Solid token
  // nor the model key lands in logs, browser history or Referer headers.
  const exchangeCredentials = async (): Promise<string | undefined> => {
    const headers: Record<string, string> = {};

    try {
      if (isSolidLoggedIn) {
        const token = await getAccessToken();
        if (token) headers.Authorization = `Bearer ${token}`;
      }
    } catch (error) {
      console.error('Could not read the Solid token:', error);
    }

    const apiKey = getKey(providerForProfile(selectedLLMProfile));
    if (apiKey) headers['X-LLM-Api-Key'] = apiKey;

    if (Object.keys(headers).length === 0) return undefined;

    try {
      const response = await api.post<{ credentials_ref: string }>(
        '/api/v1/agent/credentials',
        null,
        { headers },
      );
      return response.data.credentials_ref;
    } catch (error) {
      console.error('Could not hand over the credentials:', error);
      return undefined;
    }
  };

  // Handle agent mode submission - uses orchestrating agent for intelligent routing
  const handleAgentSubmit = async () => {
    const currentRequestTimestamp = new Date().toISOString();
    querySuccessfullyProcessedRef.current = false;
    const userQuery = chatInput.trim();
    setCurrentUserQuery(userQuery);

    const userMessage: ChatMessage = {
      key: `user-agent-${Date.now()}`,
      id: `user-agent-${Date.now()}`,
      sender: 'user',
      message: userQuery,
      timestamp: currentRequestTimestamp,
      is_user_message: true,
    };
    handleChatHistoryChange(prev => [...prev, userMessage]);
    setChatInput('');
    setIsChatLoading(true);

    // Create new response group for ChatGPT-style reasoning display
    // Each query gets its own reasoning section linked to the user message
    const newGroup = createResponseGroup(userMessage.key);
    setActiveResponseGroup(newGroup);

    // Exchange the Solid token for a short-lived reference. EventSource cannot
    // set headers, so only the reference may travel in the stream URL.
    if (!ensureApiKeyAvailable()) {
      setIsChatLoading(false);
      return;
    }

    const credentialsRef = await exchangeCredentials();

    // Always use the agent pipeline - Solid mode is handled via parameters
    // The agent will use Comunica for DATA_EXTRACTION when solid_mode is true
    const params = new URLSearchParams({
      message: userQuery,
      user_for_data: workspaceId || '',
      llm_profile: selectedLLMProfile,
      request_timestamp: currentRequestTimestamp,
      agentic_reasoning_enabled: agenticReasoningEnabled.toString(),
      internal_reasoning_enabled: internalReasoningEnabled.toString(),
      few_shot_prompting_enabled: fewShotPromptingEnabled.toString(),
      interactive_mode: interactiveMode.toString(),
      auto_execute_plans: autoExecutePlans.toString(),
      // Solid/Comunica integration parameters
      solid_mode: (isSolidLoggedIn && !!catalogId).toString(),
      catalog_id: catalogId?.toString() || '',
      catalog_url: catalogUrl || '',
    });

    if (credentialsRef) {
      params.append('credentials_ref', credentialsRef);
    }

    // Add session_id if we have one
    if (activeTab?.sessionId) {
      params.append('session_id', activeTab.sessionId);
    }

    const sseConfig = {
      url: `${api.defaults.baseURL}/api/v1/agent/chat?${params.toString()}`,
      heartbeatTimeout: 120000
    };

    connectToEventStream(
      sseConfig,
      createPipelineEventHandlers(),
      querySuccessfullyProcessedRef
    );
  };

  // Handle follow-up submission - now uses unified agent/chat endpoint
  const handleFollowUpSubmit = async () => {
    const sessionId = activeTab?.sessionId || activeSession?.id;
    if (!chatInput.trim() || isChatLoading || !sessionId) return;

    const currentRequestTimestamp = new Date().toISOString();
    const userMessage: ChatMessage = {
      key: `user-followup-${Date.now()}`,
      id: `user-followup-${Date.now()}`,
      sender: 'user',
      message: chatInput.trim(),
      timestamp: currentRequestTimestamp,
      is_user_message: true,
    };
    handleChatHistoryChange(prev => [...prev, userMessage]);
    setChatInput('');
    setIsChatLoading(true);

    // Create new response group for ChatGPT-style reasoning display
    // Each query gets its own reasoning section linked to the user message
    const newGroup = createResponseGroup(userMessage.key);
    setActiveResponseGroup(newGroup);

    // Exchange the Solid token for a short-lived reference. EventSource cannot
    // set headers, so only the reference may travel in the stream URL.
    if (!ensureApiKeyAvailable()) {
      setIsChatLoading(false);
      return;
    }

    const credentialsRef = await exchangeCredentials();

    // Use unified agent/chat endpoint with all parameters including Solid mode
    // This ensures follow-up queries have full context access
    const params = new URLSearchParams({
      message: userMessage.message,
      user_for_data: workspaceId || '',
      llm_profile: selectedLLMProfile,
      session_id: sessionId,  // Critical: includes session for context loading
      request_timestamp: currentRequestTimestamp,
      agentic_reasoning_enabled: agenticReasoningEnabled.toString(),
      internal_reasoning_enabled: internalReasoningEnabled.toString(),
      few_shot_prompting_enabled: fewShotPromptingEnabled.toString(),
      interactive_mode: interactiveMode.toString(),
      auto_execute_plans: autoExecutePlans.toString(),
      // Include Solid/Comunica parameters for follow-up queries
      solid_mode: (isSolidLoggedIn && !!catalogId).toString(),
      catalog_id: catalogId?.toString() || '',
      catalog_url: catalogUrl || '',
    });

    if (credentialsRef) {
      params.append('credentials_ref', credentialsRef);
    }

    const sseConfig = {
      url: `${api.defaults.baseURL}/api/v1/agent/chat?${params.toString()}`,
      heartbeatTimeout: 120000
    };

    // Use same handlers as main chat - agent handles routing intelligently
    connectToEventStream(sseConfig, createPipelineEventHandlers(), querySuccessfullyProcessedRef);
  };

  // Handle clarification response
  const handleChatClarificationResponse = (userResponse: string) => {
    setIsChatLoading(true);

    const params = new URLSearchParams({
      user_response: userResponse,
      workspace_id: clarificationContext.workspace_id,
      original_user_query: clarificationContext.original_user_query,
      initial_llm_reasoning: clarificationContext.initial_llm_reasoning,
      clarification_question: clarificationContext.clarification_question,
      validated_models_json: clarificationContext.validated_models_json,
      llm_profile: selectedLLMProfile,
      agentic_reasoning_enabled: agenticReasoningEnabled.toString(),
      internal_reasoning_enabled: internalReasoningEnabled.toString(),
      few_shot_prompting_enabled: fewShotPromptingEnabled.toString(),
      mode: pipelineMode === 'esg_reporting' ? 'esg' : 'general',
      interactive_mode: interactiveMode.toString()
    });

    const sseConfig = {
      url: `${api.defaults.baseURL}/api/v1/chat/continue-pipeline?${params.toString()}`,
      heartbeatTimeout: 120000
    };

    const clarificationHandlers: EventHandlers = {
      ...createPipelineEventHandlers(),
      onEndStream: () => {
        console.log('[Chat Clarification] Stream ended successfully by server.');
        setIsChatLoading(false);
        setIsWaitingForClarification(false);
        setClarificationContext(null);
      },
      onError: (error) => {
        console.error('Chat clarification EventSource failed:', error);
        setIsChatLoading(false);
        handleChatHistoryChange(prev => [...prev, {
          key: `error-clarification-${Date.now()}`,
          sender: 'System',
          message: 'Verbindung bei der Fortsetzung fehlgeschlagen.',
          timestamp: new Date().toISOString(),
          is_user_message: false,
        }]);
      }
    };

    connectToEventStream(sseConfig, clarificationHandlers);
  };

  // Export functions
  //
  // The query is written client side: it is already in the browser, so a
  // round trip to the backend would add nothing.
  const handleSparqlExport = (sparqlQuery: string, format: string) => {
    setExportingQuery(sparqlQuery);
    try {
      const payload =
        format === 'json'
          ? JSON.stringify({ sparql_query: sparqlQuery }, null, 2)
          : format === 'xml'
            ? `<?xml version="1.0" encoding="UTF-8"?>
<query><![CDATA[${sparqlQuery}]]></query>`
            : sparqlQuery;

      const mimeType =
        format === 'json' ? 'application/json' : format === 'xml' ? 'application/xml' : 'text/plain';

      const blob = new Blob([payload], { type: `${mimeType};charset=utf-8` });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `sparql_query.${format === 'tsv' || format === 'csv' ? 'rq' : format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.success(`Query exported as ${format.toUpperCase()}`);
    } catch (error) {
      console.error('Export error:', error);
      message.error('Export failed. Please try again.');
    } finally {
      setExportingQuery(null);
    }
  };

  const handleCopyQuery = (sparqlQuery: string) => {
    navigator.clipboard.writeText(sparqlQuery).then(() => {
      message.success('SPARQL query copied to clipboard');
    }).catch((error) => {
      console.error('Copy failed:', error);
      message.error('Failed to copy query');
    });
  };

  const handleResultsExport = (variables: string[], results: any[], format: string) => {
    try {
      const sparqlJsonResults = {
        head: { vars: variables },
        results: {
          bindings: results.map(row => {
            const binding: any = {};
            variables.forEach(variable => {
              if (row[variable]) {
                binding[variable] = {
                  type: row[variable].type || 'literal',
                  value: row[variable].value || row[variable]
                };
              }
            });
            return binding;
          })
        }
      };

      let exportData: string;
      let filename: string;
      let mimeType: string;

      const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');

      switch (format) {
        case 'json':
          exportData = JSON.stringify(sparqlJsonResults, null, 2);
          filename = `sparql_results_${timestamp}.json`;
          mimeType = 'application/json';
          break;
        case 'csv':
          const csvHeader = variables.join(',');
          const csvRows = results.map(row => 
            variables.map(variable => {
              const value = row[variable]?.value || row[variable] || '';
              return `"${String(value).replace(/"/g, '""')}"`;
            }).join(',')
          );
          exportData = [csvHeader, ...csvRows].join('\n');
          filename = `sparql_results_${timestamp}.csv`;
          mimeType = 'text/csv';
          break;
        case 'tsv':
          const tsvHeader = variables.join('\t');
          const tsvRows = results.map(row => 
            variables.map(variable => {
              const value = row[variable]?.value || row[variable] || '';
              return String(value).replace(/\t/g, ' ');
            }).join('\t')
          );
          exportData = [tsvHeader, ...tsvRows].join('\n');
          filename = `sparql_results_${timestamp}.tsv`;
          mimeType = 'text/tab-separated-values';
          break;
        default:
          throw new Error('Unsupported format');
      }

      const blob = new Blob([exportData], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.success(`Results exported as ${format.toUpperCase()}`);
    } catch (error) {
      console.error('Export error:', error);
      message.error('Export failed. Please try again.');
    }
  };

  // Handle correction of last query by triggering error analysis pipeline
  const handleCorrectLastQuery = async () => {
    // Find the last message with SPARQL results - check for any combination of SPARQL properties
    const lastResultMessage = chatHistory
      .slice()
      .reverse()
      .find(msg => (msg.sparql_query || msg.sparql_results) && msg.user_query);

    if (!lastResultMessage || (!lastResultMessage.sparql_query && !lastResultMessage.sparql_results) || !lastResultMessage.user_query) {
      message.error('Keine SPARQL-Query zur Korrektur gefunden');
      return;
    }

    const correctionMessageKey = `correction-${Date.now()}`;

    try {
      setIsChatLoading(true);

      // Create correction message in chat
      const correctionMessage: ChatMessage = {
        key: correctionMessageKey,
        id: correctionMessageKey,
        sender: 'SPARQL Korrektur',
        message: t('chat.correcting'),
        timestamp: new Date().toISOString(),
        is_user_message: false,
        is_streaming: true,
        step_id: 'correction_started'
      };

      handleChatHistoryChange(prev => [...prev, correctionMessage]);

      // Prepare correction request
      const correctionRequest = {
        workspace_id: workspaceId,
        sparql_query: lastResultMessage.sparql_query,
        user_query: lastResultMessage.user_query,
        semantic_models_content: lastResultMessage.model_info_blocks || '',
        selected_models: lastResultMessage.selected_models || []
      };

      // Call correction API
      const response = await fetch(`${api.defaults.baseURL}/api/v1/sparql/correct`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(correctionRequest)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Korrektur fehlgeschlagen');
      }

      const correctionResult = await response.json();

      // If query was corrected, execute the new query automatically and show results
      if (correctionResult.corrected && correctionResult.final_query) {
        // Update message to show query execution
        handleChatHistoryChange(prev => prev.map(msg =>
          msg.key === correctionMessageKey
            ? {
                ...msg,
                message: t('chat.correctedRunning'),
                is_streaming: true
              }
            : msg
        ));

        // Execute the corrected query and show results like a normal query
        const executionResponse = await fetch(`${api.defaults.baseURL}/api/v1/sparql/execute`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            workspace_id: workspaceId,
            sparql_query: correctionResult.final_query,
            user_query: lastResultMessage.user_query,
            semantic_models_content: lastResultMessage.model_info_blocks || ''
          })
        });

        if (executionResponse.ok) {
          const executionResult = await executionResponse.json();

          // Replace correction message with successful results
          handleChatHistoryChange(prev => prev.map(msg =>
            msg.key === correctionMessageKey
              ? {
                  ...msg,
                  sender: 'SPARQL Ergebnis (Korrigiert)',
                  message: t('chat.correctedSuccess'),
                  is_streaming: false,
                  step_id: 'sparql_execution_completed',
                  sparql_query: correctionResult.final_query,
                  sparql_variables: executionResult.results?.head?.vars || [],
                  sparql_results: executionResult.results?.results?.bindings || [],
                  user_query: lastResultMessage.user_query,
                  model_info_blocks: lastResultMessage.model_info_blocks,
                  selected_models: lastResultMessage.selected_models
                }
              : msg
          ));

          message.success(t('chat.correctedSuccess'));
        } else {
          throw new Error(t('chat.correctedFailed'));
        }
      } else {
        // No correction was needed
        handleChatHistoryChange(prev => prev.map(msg =>
          msg.key === correctionMessageKey
            ? {
                ...msg,
                message: t('chat.noCorrectionNeeded'),
                is_streaming: false,
                step_id: 'correction_completed'
              }
            : msg
        ));

        message.info(t('chat.alreadyOptimal'));
      }

    } catch (error) {
      console.error('Correction error:', error);

      // Update correction message with error
      handleChatHistoryChange(prev => prev.map(msg =>
        msg.key === correctionMessageKey
          ? {
              ...msg,
              message: `❌ **Korrektur fehlgeschlagen**\n\n${error instanceof Error ? error.message : 'Unbekannter Fehler'}`,
              is_streaming: false,
              step_id: 'correction_failed'
            }
          : msg
      ));

      message.error('Korrektur fehlgeschlagen: ' + (error instanceof Error ? error.message : 'Unbekannter Fehler'));
    } finally {
      setIsChatLoading(false);
    }
  };

  // Menu generators
  const getSparqlExportMenu = (sparqlQuery: string): MenuProps => ({
    items: [
      {
        key: 'json',
        label: 'Export as JSON',
        onClick: () => handleSparqlExport(sparqlQuery, 'json'),
      },
      {
        key: 'csv',
        label: 'Export as CSV',
        onClick: () => handleSparqlExport(sparqlQuery, 'csv'),
      },
      {
        key: 'tsv',
        label: 'Export as TSV',
        onClick: () => handleSparqlExport(sparqlQuery, 'tsv'),
      },
      {
        key: 'xml',
        label: 'Export as XML',
        onClick: () => handleSparqlExport(sparqlQuery, 'xml'),
      },
    ],
  });

  const getResultsExportMenu = (variables: string[], results: any[]): MenuProps => ({
    items: [
      {
        key: 'json',
        label: 'Export as JSON',
        onClick: () => handleResultsExport(variables, results, 'json'),
      },
      {
        key: 'csv',
        label: 'Export as CSV',
        onClick: () => handleResultsExport(variables, results, 'csv'),
      },
      {
        key: 'tsv',
        label: 'Export as TSV',
        onClick: () => handleResultsExport(variables, results, 'tsv'),
      },
    ],
  });

  const getSuggestionMenu = (): MenuProps => ({
    items: [
      {
        key: 'suggestion1',
        label: 'T9-Switch Bestandteile',
        onClick: () => setChatInput('Extrahiere die Namen der Bestandteile, deren Anzahl, Gewicht und Hersteller des Produktes T9-Switch. Sortiere die Ausgabe alphabetisch nach den Namen der Bestandteile.'),
      },
      {
        key: 'suggestion2',
        label: 'AgCd0 Materialanteile',
        onClick: () => setChatInput(t('chat.exampleMaterials')),
      },
      {
        key: 'suggestion3',
        label: 'Ladestationen Vergleich',
        onClick: () => setChatInput('Vergleiche die Anzahl der Ladestationen in Wuppertal und Rostock.'),
      },
      {
        key: 'suggestion4',
        label: 'CO2 Joghurtbecher',
        onClick: () => setChatInput(t('chat.exampleEmissions')),
      },
    ],
  });

  // Pipeline mode handlers
  const llmOptions = [
    { value: 'ollama_local_gemma3', label: 'Ollama Lokal (Gemma3 4B)' },
    { value: 'ollama_local_phi3mini', label: 'Ollama Lokal (Phi3-mini 3.8B)' },
    { value: 'ollama_remote_llama31_70b', label: 'Ollama Remote (Llama3.3 70B)' },
    { value: 'deepseek_chat', label: 'DeepSeek Chat' },
    { value: 'fireworks_deepseek_chat', label: 'DeepSeek (via Fireworks)' },
    { value: 'fireworks_qwen3_30b', label: 'Fireworks Qwen3 30B' },
    { value: 'openai_gpt4o', label: 'OpenAI GPT-4o' },
  ];

  return (
    <div style={{
      display: 'flex',
      gap: '16px',
      height: 'calc(100vh - 80px)',
      margin: '16px',
      padding: '16px',
      background: 'linear-gradient(135deg, #E4E8EB 0%, #f0f2f4 100%)',
      borderRadius: '28px'
    }}>
      {/* Sidebar with Tabs */}
      <ChatSidebar
        tabs={tabs}
        activeTabId={activeTabId}
        onTabClick={handleTabClick}
        onTabClose={handleTabClose}
        onNewTab={handleNewTab}
      />

      {/* Main Chat Area */}
      <div
        style={{
          flex: 1,
          background: '#ffffff',
          borderRadius: '20px',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 4px 24px rgba(22, 68, 117, 0.08)',
          overflow: 'hidden',
          minHeight: 0
        }}
      >

        {/* Chat Title Header - Shows active tab title */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px',
          flexShrink: 0
        }}>
          <Typography.Title
            level={3}
            style={{
              margin: 0,
              color: '#164475',
              fontWeight: 600,
              fontSize: '24px'
            }}
          >
            {activeTab?.title || 'Neue Analyse'}
          </Typography.Title>

          {/* Session Status - Compact version */}
          <SessionManager />
        </div>

        <div
          ref={chatContainerRef}
          style={{
            flex: 1,
            overflow: 'auto',
            border: '1px solid var(--color-gray-200)',
            padding: '24px',
            marginBottom: '16px',
            background: '#ffffff',
            borderRadius: '16px',
            boxShadow: 'inset 0 2px 8px rgba(22, 68, 117, 0.04)',
            position: 'relative',
            minHeight: 0
          }}
        >
          {activeTab && (
            <ChatMessageList
              chatHistory={chatHistory}
              activeStreamIds={activeStreamIds}
              isChatLoading={isChatLoading}
              exportingQuery={exportingQuery}
              onCopyQuery={handleCopyQuery}
              onExportResults={handleResultsExport}
              getSparqlExportMenu={getSparqlExportMenu}
              getResultsExportMenu={getResultsExportMenu}
              responseGroups={responseGroups}
              activeResponseGroup={activeResponseGroup}
              expandedGroups={expandedGroups}
              onToggleGroupExpand={toggleGroupExpansion}
            />
          )}
        </div>

        {showKIConfiguration && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(22, 68, 117, 0.03) 0%, rgba(248, 250, 252, 0.5) 100%)',
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid rgba(22, 68, 117, 0.1)',
            marginBottom: '16px'
          }}>
            <Typography.Text style={{
              color: '#164475',
              fontWeight: 600,
              fontSize: '14px',
              letterSpacing: '0.2px',
              display: 'block',
              marginBottom: '12px'
            }}>
              KI-Konfiguration:
            </Typography.Text>
            <Space direction="horizontal" size="large" wrap>
              <Form.Item label={
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 500 }}>
                  Agentic Self-Reflect
                </span>
              } valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch
                  checked={agenticReasoningEnabled}
                  onChange={setAgenticReasoningEnabled}
                  disabled={isChatLoading}
                  style={{
                    background: agenticReasoningEnabled ? 'linear-gradient(135deg, #164475 0%, #123a64 100%)' : undefined
                  }}
                />
              </Form.Item>
              <Form.Item label={
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 500 }}>
                  Internal Reasoning
                </span>
              } valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch
                  checked={internalReasoningEnabled}
                  onChange={setInternalReasoningEnabled}
                  disabled={isChatLoading}
                  style={{
                    background: internalReasoningEnabled ? 'linear-gradient(135deg, #164475 0%, #123a64 100%)' : undefined
                  }}
                />
              </Form.Item>
              <Form.Item label={
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 500 }}>
                  Few-Shot Prompting
                </span>
              } valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch
                  checked={fewShotPromptingEnabled}
                  onChange={setFewShotPromptingEnabled}
                  disabled={isChatLoading}
                  style={{
                    background: fewShotPromptingEnabled ? 'linear-gradient(135deg, #164475 0%, #123a64 100%)' : undefined
                  }}
                />
              </Form.Item>
              <Form.Item label={
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 500 }}>
                  {t('chat.agentMode')}
                </span>
              } valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch
                  checked={useAgentMode}
                  onChange={setUseAgentMode}
                  disabled={isChatLoading}
                  style={{
                    background: useAgentMode ? 'linear-gradient(135deg, #C6712F 0%, #a85f28 100%)' : undefined
                  }}
                />
              </Form.Item>
              <Form.Item label={
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: 500 }}>
                  {t('chat.autoExecute')}
                </span>
              } valuePropName="checked" style={{ marginBottom: 0 }}>
                <Switch
                  checked={autoExecutePlans}
                  onChange={setAutoExecutePlans}
                  disabled={isChatLoading || !useAgentMode}
                  style={{
                    background: autoExecutePlans ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : undefined
                  }}
                />
              </Form.Item>
            </Space>
          </div>
        )}

        {/* Model Selection Interface */}
        {isWaitingForModelSelection && modelSelectionContext && (
          <ModelSelector
            selectedModels={selectedModelsForConfirmation}
            availableModels={modelSelectionContext.available_models || []}
            onSelectionChange={handleModelSelection}
            onConfirm={handleConfirmModels}
            onCancel={handleCancelModelSelection}
            isLoading={isChatLoading}
          />
        )}

        {/* Plan Confirmation Interface */}
        {isWaitingForPlanConfirmation && pendingPlan && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(248, 250, 252, 0.5) 100%)',
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid rgba(16, 185, 129, 0.2)',
            marginBottom: '16px',
            flexShrink: 0
          }}>
            <Typography.Text style={{
              color: '#059669',
              fontWeight: 600,
              fontSize: '14px',
              letterSpacing: '0.2px',
              display: 'block',
              marginBottom: '12px'
            }}>
              {t('chat.planNeedsConfirm')}
            </Typography.Text>
            <Typography.Text style={{
              color: '#64748b',
              fontSize: '13px',
              display: 'block',
              marginBottom: '16px'
            }}>
              {t('chat.planAskRun')}
            </Typography.Text>
            <Space>
              <Button
                type="primary"
                onClick={handleConfirmPlan}
                style={{
                  background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 500
                }}
              >
                {t('chat.planRun')}
              </Button>
              <Button
                onClick={handleCancelPlan}
                style={{
                  borderRadius: '8px',
                  fontWeight: 500
                }}
              >
                ❌ Abbrechen
              </Button>
            </Space>
          </div>
        )}

        {/* User Input Request Interface (when agent needs help) */}
        {isWaitingForUserInput && userInputContext && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(234, 179, 8, 0.08) 0%, rgba(248, 250, 252, 0.5) 100%)',
            padding: '16px',
            borderRadius: '12px',
            border: '1px solid rgba(234, 179, 8, 0.2)',
            marginBottom: '16px',
            flexShrink: 0
          }}>
            <Typography.Text style={{
              color: '#ca8a04',
              fontWeight: 600,
              fontSize: '14px',
              letterSpacing: '0.2px',
              display: 'block',
              marginBottom: '8px'
            }}>
              {t('chat.inputNeeded')}
            </Typography.Text>
            <Typography.Text style={{
              color: '#64748b',
              fontSize: '13px',
              display: 'block'
            }}>
              {t('chat.inputNeededHint')}
            </Typography.Text>
          </div>
        )}

        <div style={{ flexShrink: 0 }}>
          <ChatInput
            chatInput={chatInput}
            isChatLoading={isChatLoading}
            isWaitingForClarification={isWaitingForClarification}
            isFollowUpMode={!!isFollowUpMode}
            activeSession={activeSession}
            onChatInputChange={setChatInput}
            onSubmit={handleChatSubmit}
            getSuggestionMenu={getSuggestionMenu}
            onCorrectLastQuery={handleCorrectLastQuery}
            hasResultsDisplayed={hasResultsDisplayed || false}
            selectedLLMProfile={selectedLLMProfile}
            onLLMChange={setSelectedLLMProfile}
            llmOptions={llmOptions}
            interactiveMode={interactiveMode}
            onInteractiveModeChange={setInteractiveMode}
            autoExecutePlans={autoExecutePlans}
            onAutoExecutePlansChange={setAutoExecutePlans}
            useAgentMode={useAgentMode}
            showKIConfiguration={showKIConfiguration}
            onToggleKIConfiguration={toggleKIConfiguration}
          />
        </div>
      </div>
      <ApiKeySettingsModal
        visible={apiKeyPromptVisible}
        onClose={() => setApiKeyPromptVisible(false)}
      />
    </div>
  );
}