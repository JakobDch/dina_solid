import { useEffect, useRef } from 'react';
import { EventSourcePolyfill, type Event as PolyfillEvent } from 'event-source-polyfill';

export interface EventHandlers {
  onPipelineUpdate?: (data: any) => void;
  onClarificationRequired?: (data: any) => void;
  onModelSelectionRequired?: (data: any) => void;
  onMessageStreamStart?: (data: any) => void;
  onMessageStreamChunk?: (data: any) => void;
  onMessageStreamEnd?: (data: any) => void;
  onEndStream?: (data?: { session_id?: string; message?: string; step_id?: string }) => void;
  onError?: (error: PolyfillEvent) => void;
  // Agent-specific event handlers
  onCorpusInfo?: (data: any) => void;
  onVisualizationResult?: (data: any) => void;
  onCalculationResult?: (data: any) => void;
  onPipelineError?: (data: any) => void;
  // Plan-based agent event handlers
  onPlanConfirmationRequired?: (data: any) => void;
  onIntermediateMessage?: (data: any) => void;
  onPlanStepUpdate?: (data: any) => void;
  onUserInputRequired?: (data: any) => void;
  // Agent clarification required (plan paused waiting for user answer)
  onAgentClarificationRequired?: (data: any) => void;
  // Solid/Comunica integration - agent requests frontend to execute via Comunica
  onComunicaExecutionRequired?: (data: any) => void;
}

export interface SSEConfig {
  url: string;
  heartbeatTimeout?: number;
}

export function useServerSentEvents() {
  const eventSourceRef = useRef<EventSourcePolyfill | null>(null);

  const connectToEventStream = (
    config: SSEConfig,
    handlers: EventHandlers,
    querySuccessfullyProcessedRef?: React.MutableRefObject<boolean>
  ) => {
    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSourcePolyfill(config.url, {
      heartbeatTimeout: config.heartbeatTimeout || 120000
    });

    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      console.log('[SSE onopen] EventSource connection successfully opened.');
    };

    // Pipeline update events
    if (handlers.onPipelineUpdate) {
      eventSource.addEventListener('pipeline_update', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const serverMessageData = JSON.parse((event as MessageEvent).data as string);
          handlers.onPipelineUpdate!(serverMessageData);
        } catch (e) {
          console.error('Error parsing pipeline_update event:', e);
        }
      });
    }

    // Clarification required events
    if (handlers.onClarificationRequired) {
      eventSource.addEventListener('user_clarification_required', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const parsedData = JSON.parse((event as MessageEvent).data as string);
          handlers.onClarificationRequired!(parsedData);
        } catch (e) {
          console.error('Error parsing user_clarification_required event:', e);
        }
      });
    }

    // Model selection required events
    if (handlers.onModelSelectionRequired) {
      eventSource.addEventListener('pipeline_interactive_checkpoint', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const parsedData = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Model selection required event received:', parsedData);
          handlers.onModelSelectionRequired!(parsedData);
        } catch (e) {
          console.error('Error parsing pipeline_interactive_checkpoint event:', e);
        }
      });
    }

    // Streaming message events
    if (handlers.onMessageStreamStart) {
      eventSource.addEventListener('message_stream_start', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          handlers.onMessageStreamStart!(data);
        } catch (e) {
          console.error('Error parsing message_stream_start event:', e);
        }
      });
    }

    if (handlers.onMessageStreamChunk) {
      eventSource.addEventListener('message_stream_chunk', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          handlers.onMessageStreamChunk!(data);
        } catch (e) {
          console.error('Error parsing message_stream_chunk event:', e);
        }
      });
    }

    if (handlers.onMessageStreamEnd) {
      eventSource.addEventListener('message_stream_end', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          handlers.onMessageStreamEnd!(data);
        } catch (e) {
          console.error('Error parsing message_stream_end event:', e);
        }
      });
    }

    // Agent corpus info events
    if (handlers.onCorpusInfo) {
      eventSource.addEventListener('corpus_info', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Corpus info event received:', data);
          handlers.onCorpusInfo!(data);
        } catch (e) {
          console.error('Error parsing corpus_info event:', e);
        }
      });
    }

    // Agent visualization result events
    if (handlers.onVisualizationResult) {
      eventSource.addEventListener('visualization_result', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Visualization result event received:', data);
          handlers.onVisualizationResult!(data);
        } catch (e) {
          console.error('Error parsing visualization_result event:', e);
        }
      });
    }

    // Agent calculation result events
    if (handlers.onCalculationResult) {
      eventSource.addEventListener('calculation_result', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Calculation result event received:', data);
          handlers.onCalculationResult!(data);
        } catch (e) {
          console.error('Error parsing calculation_result event:', e);
        }
      });
    }

    // Pipeline error events (from agent)
    if (handlers.onPipelineError) {
      eventSource.addEventListener('pipeline_error', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Pipeline error event received:', data);
          handlers.onPipelineError!(data);
        } catch (e) {
          console.error('Error parsing pipeline_error event:', e);
        }
      });
    }

    // Plan confirmation required events (when auto_execute_plans is false)
    if (handlers.onPlanConfirmationRequired) {
      eventSource.addEventListener('plan_confirmation_required', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Plan confirmation required event received:', data);
          handlers.onPlanConfirmationRequired!(data);
        } catch (e) {
          console.error('Error parsing plan_confirmation_required event:', e);
        }
      });
    }

    // Intermediate message events (natural language progress updates)
    if (handlers.onIntermediateMessage) {
      eventSource.addEventListener('intermediate_message', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Intermediate message event received:', data);
          handlers.onIntermediateMessage!(data);
        } catch (e) {
          console.error('Error parsing intermediate_message event:', e);
        }
      });
    }

    // Plan step update events (step started, completed, skipped, failed)
    if (handlers.onPlanStepUpdate) {
      eventSource.addEventListener('plan_step_update', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Plan step update event received:', data);
          handlers.onPlanStepUpdate!(data);
        } catch (e) {
          console.error('Error parsing plan_step_update event:', e);
        }
      });
    }

    // User input required events (when agent needs help with errors)
    if (handlers.onUserInputRequired) {
      eventSource.addEventListener('user_input_required', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] User input required event received:', data);
          handlers.onUserInputRequired!(data);
        } catch (e) {
          console.error('Error parsing user_input_required event:', e);
        }
      });
    }

    // Agent clarification required events (plan paused waiting for user answer)
    if (handlers.onAgentClarificationRequired) {
      eventSource.addEventListener('agent_clarification_required', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Agent clarification required event received:', data);
          handlers.onAgentClarificationRequired!(data);
        } catch (e) {
          console.error('Error parsing agent_clarification_required event:', e);
        }
      });
    }

    // Comunica execution required events (Solid mode - frontend should execute via Comunica)
    if (handlers.onComunicaExecutionRequired) {
      eventSource.addEventListener('comunica_execution_required', (event) => {
        try {
          if (!('data' in event) || typeof (event as MessageEvent).data !== 'string') return;
          const data = JSON.parse((event as MessageEvent).data as string);
          console.log('[SSE] Comunica execution required event received:', data);
          handlers.onComunicaExecutionRequired!(data);
        } catch (e) {
          console.error('Error parsing comunica_execution_required event:', e);
        }
      });
    }

    // End stream events
    if (handlers.onEndStream) {
      eventSource.addEventListener('end_stream', (event) => {
        console.log('[Chat] Stream ended successfully by server.');
        if (querySuccessfullyProcessedRef) {
          querySuccessfullyProcessedRef.current = true;
        }
        // Parse event data to extract session_id
        let eventData: { session_id?: string; message?: string; step_id?: string } | undefined;
        try {
          if ('data' in event && typeof (event as MessageEvent).data === 'string') {
            eventData = JSON.parse((event as MessageEvent).data as string);
            if (eventData?.session_id) {
              console.log('[SSE] Session ID received from server:', eventData.session_id);
            }
          }
        } catch (e) {
          console.warn('Could not parse end_stream event data:', e);
        }
        handlers.onEndStream!(eventData);
        eventSource.close();
      });
    }

    // Error handling
    eventSource.onerror = (event: PolyfillEvent) => {
      if (querySuccessfullyProcessedRef?.current) {
        console.log("[Chat] onerror triggered, but stream was already closed successfully. Ignoring.");
        return;
      }

      console.error('EventSource failed with a real error:', event);
      
      if (handlers.onError) {
        handlers.onError(event);
      }
      
      eventSource.close();
    };

    return eventSource;
  };

  const closeConnection = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  };

  // Close the stream when the component unmounts. Without this the connection
  // survives navigation and the server keeps writing to a listener that no
  // longer exists.
  useEffect(() => closeConnection, []);

  return {
    connectToEventStream,
    closeConnection
  };
}