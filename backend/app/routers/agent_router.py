"""
Agent Router for DINa ESG Reporting

Provides the /api/v1/agent/chat endpoint for the orchestrating agent.
"""

import json
import logging
import os
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
import redis.asyncio as aioredis

from ..db import get_session
from ..config import (
    get_settings,
    get_llm_for_profile,
    describe_llm_profiles,
    MissingApiKeyError,
    AppSettings,
)
from ..orchestrating_agent import (
    OrchestratingAgent,
    AgentContext,
    ResultsReference,
    MAX_SPARQL_RESULTS_IN_CONTEXT,
    MAX_CONVERSATION_HISTORY
)
from ..models import ChatSession, ComunicaResultsRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/2")  # Use db 2 for agent cache

# Global Redis client (lazy initialized)
_redis_client: Optional[aioredis.Redis] = None


async def get_redis_client() -> aioredis.Redis:
    """Get or create Redis client for results caching"""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return _redis_client


async def load_agent_context(
    session_id: str,
    workspace_id: str,
    db: Session,
    redis_client=None
) -> Optional[AgentContext]:
    """
    Load agent context from an existing chat session.

    Implements intelligent context management:
    - Small result sets (≤100 rows) are loaded directly into context
    - Large result sets are stored as ResultsReference with only a sample
    - Conversation history is limited via sliding window

    Args:
        session_id: The chat session ID
        workspace_id: The workspace ID
        db: Database session
        redis_client: Optional Redis client for loading cached results
    """
    try:
        session = db.exec(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.workspace_id == workspace_id
            )
        ).first()

        if not session:
            return None

        context = AgentContext(workspace_id=workspace_id)
        context.session_id = str(session.id)
        context.last_data_sources = session.selected_models or []
        context.model_info_blocks = session.model_info_blocks
        context.model_check_hints = session.model_check_hints
        context.last_user_query = session.initial_query

        # Set Redis client for lazy loading if available
        if redis_client:
            context.set_redis_client(redis_client)

        # Check for existing results_ref in session (from previous cached results)
        if hasattr(session, 'results_ref_data') and session.results_ref_data:
            try:
                ref_data = session.results_ref_data
                if isinstance(ref_data, str):
                    ref_data = json.loads(ref_data)
                context.results_ref = ResultsReference.from_dict(ref_data)
                context.last_sparql_variables = session.last_sparql_variables or []
                context.last_sparql_query = session.last_sparql_query
                logger.info(f"[Agent Context] Loaded cached results reference for session {session_id}")
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"[Agent Context] Failed to load results_ref: {e}")

        # Load SPARQL results with intelligent context management
        elif session.last_sparql_results:
            results_data = session.last_sparql_results
            if isinstance(results_data, str):
                results_data = json.loads(results_data)

            # Parse results into list format
            results_list = []
            if isinstance(results_data, list):
                results_list = results_data
            elif isinstance(results_data, dict):
                bindings = results_data.get("results", {}).get("bindings")
                if bindings is not None:
                    results_list = bindings
                else:
                    results_list = results_data.get("bindings", [])

            # Apply context size management
            if len(results_list) <= MAX_SPARQL_RESULTS_IN_CONTEXT:
                # Small enough: load directly
                context.last_sparql_results = results_list
                logger.info(f"[Agent Context] Loaded {len(results_list)} results directly into context")
            else:
                # Too large: create reference with sample (if Redis available, cache will be populated on next query)
                sample_size = min(5, len(results_list))
                variables = list(results_list[0].keys()) if results_list else []

                context.results_ref = ResultsReference(
                    cache_key=f"sparql_results:{session_id}:loaded",
                    total_count=len(results_list),
                    variables=variables,
                    sample=results_list[:sample_size]
                )
                # Store full results temporarily for this session
                # They will be cached properly when store_results_to_cache is called
                context.last_sparql_results = results_list
                logger.info(
                    f"[Agent Context] Large result set ({len(results_list)} rows), "
                    f"created reference with {sample_size} sample rows"
                )

            context.last_sparql_variables = session.last_sparql_variables or []
            context.last_sparql_query = session.last_sparql_query
        else:
            # Fallback: Load from session messages
            from ..models import ChatSessionMessage
            last_message = db.exec(
                select(ChatSessionMessage)
                .where(
                    ChatSessionMessage.session_id == session.id,
                    ChatSessionMessage.sparql_results.isnot(None)
                )
                .order_by(ChatSessionMessage.timestamp.desc())
            ).first()

            if last_message and last_message.sparql_results:
                try:
                    results_data = last_message.sparql_results
                    if isinstance(results_data, str):
                        results_data = json.loads(results_data)
                    results_list = results_data.get("results", {}).get("bindings", [])

                    # Apply same context size management
                    if len(results_list) <= MAX_SPARQL_RESULTS_IN_CONTEXT:
                        context.last_sparql_results = results_list
                    else:
                        sample_size = min(5, len(results_list))
                        variables = results_data.get("head", {}).get("vars", [])
                        context.results_ref = ResultsReference(
                            cache_key=f"sparql_results:{session_id}:msg",
                            total_count=len(results_list),
                            variables=variables,
                            sample=results_list[:sample_size]
                        )
                        context.last_sparql_results = results_list

                    context.last_sparql_variables = results_data.get("head", {}).get("vars", [])
                    context.last_sparql_query = last_message.sparql_query
                except (json.JSONDecodeError, TypeError):
                    pass

        # Load and apply sliding window to conversation history
        from ..models import ChatSessionMessage
        messages = db.exec(
            select(ChatSessionMessage)
            .where(ChatSessionMessage.session_id == session.id)
            .order_by(ChatSessionMessage.timestamp.desc())
            .limit(MAX_CONVERSATION_HISTORY)
        ).all()

        # Reverse to get chronological order
        context.conversation_history = [
            {
                "role": "user" if msg.is_user_message else "assistant",
                "content": msg.message,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            }
            for msg in reversed(messages)
        ]

        # === NEW: Load extended context fields ===
        # Load Solid/Comunica mode settings
        if hasattr(session, 'solid_mode') and session.solid_mode:
            context.solid_mode = session.solid_mode
            context.catalog_id = session.catalog_id or ""
            context.catalog_url = session.catalog_url or ""
            logger.info(f"[Agent Context] Solid mode enabled - catalog: {context.catalog_id}")

        # Load results history from session
        if hasattr(session, 'results_history_data') and session.results_history_data:
            try:
                from ..orchestrating_agent import ResultsHistoryEntry
                for entry_data in session.results_history_data:
                    entry = ResultsHistoryEntry.from_dict(entry_data)
                    context.results_history.append(entry)
                    context._results_counter = max(context._results_counter,
                        int(entry.entry_id.split('_')[1]) if '_' in entry.entry_id else 0)
                logger.info(f"[Agent Context] Loaded {len(context.results_history)} results history entries")
            except Exception as e:
                logger.warning(f"[Agent Context] Failed to load results history: {e}")

        # Load visualization history from session
        if hasattr(session, 'visualization_history') and session.visualization_history:
            try:
                from ..orchestrating_agent import VisualizationHistoryEntry
                for entry_data in session.visualization_history:
                    entry = VisualizationHistoryEntry.from_dict(entry_data)
                    context.visualization_history.append(entry)
                    context._viz_counter = max(context._viz_counter,
                        int(entry.entry_id.split('_')[1]) if '_' in entry.entry_id else 0)
                logger.info(f"[Agent Context] Loaded {len(context.visualization_history)} visualization entries")
            except Exception as e:
                logger.warning(f"[Agent Context] Failed to load visualization history: {e}")

        # Load calculation history from session
        if hasattr(session, 'calculation_history') and session.calculation_history:
            try:
                from ..orchestrating_agent import CalculationHistoryEntry
                for entry_data in session.calculation_history:
                    entry = CalculationHistoryEntry.from_dict(entry_data)
                    context.calculation_history.append(entry)
                    context._calc_counter = max(context._calc_counter,
                        int(entry.entry_id.split('_')[1]) if '_' in entry.entry_id else 0)
                # Also restore last calculation code/results
                if context.calculation_history:
                    last_calc = context.calculation_history[-1]
                    context.last_calculation_code = last_calc.code
                    context.last_calculation_results = last_calc.result_data
                logger.info(f"[Agent Context] Loaded {len(context.calculation_history)} calculation entries")
            except Exception as e:
                logger.warning(f"[Agent Context] Failed to load calculation history: {e}")

        # Load catalog search history from session
        if hasattr(session, 'catalog_search_history') and session.catalog_search_history:
            try:
                context.catalog_search_history = session.catalog_search_history
                logger.info(f"[Agent Context] Loaded {len(context.catalog_search_history)} catalog search entries")
            except Exception as e:
                logger.warning(f"[Agent Context] Failed to load catalog search history: {e}")

        # Log context summary
        result_count = 0
        result_type = "none"
        if context.last_sparql_results:
            result_count = len(context.last_sparql_results)
            result_type = "direct"
        elif context.results_ref:
            result_count = context.results_ref.total_count
            result_type = "cached_ref"

        logger.info(f"[Agent Context] Loaded context for session {session_id}:")
        logger.info(f"  - results: {result_count} ({result_type})")
        logger.info(f"  - results_history: {len(context.results_history)} entries")
        logger.info(f"  - visualizations: {len(context.visualization_history)} entries")
        logger.info(f"  - calculations: {len(context.calculation_history)} entries")
        logger.info(f"  - variables: {context.last_sparql_variables}")
        logger.info(f"  - data sources: {context.last_data_sources}")
        logger.info(f"  - conversation history: {len(context.conversation_history)} messages (max {MAX_CONVERSATION_HISTORY})")
        logger.info(f"  - catalog_search_history: {len(context.catalog_search_history)} entries")
        logger.info(f"  - solid_mode: {context.solid_mode}")
        return context

    except Exception as e:
        logger.error(f"Error loading agent context: {e}", exc_info=True)
        return None


async def save_agent_context(
    context: AgentContext,
    db: Session,
    user_message: str = None,
    assistant_message: str = None
) -> bool:
    """
    Save the agent context to the chat session in the database.
    This ensures all data (including Comunica results) is persisted for follow-up queries.

    Args:
        context: The AgentContext to save
        db: Database session
        user_message: Optional user message to save as ChatSessionMessage
        assistant_message: Optional assistant response to save as ChatSessionMessage

    Returns:
        True if save was successful, False otherwise
    """
    if not context.session_id:
        logger.warning("[Agent Context] Cannot save context: no session_id")
        return False

    try:
        session = db.exec(
            select(ChatSession).where(ChatSession.id == context.session_id)
        ).first()

        if not session:
            logger.warning(f"[Agent Context] Session not found: {context.session_id}")
            return False

        # Update SPARQL results
        if context.last_sparql_results:
            session.last_sparql_results = context.last_sparql_results
        if context.last_sparql_variables:
            session.last_sparql_variables = context.last_sparql_variables
        if context.last_sparql_query:
            session.last_sparql_query = context.last_sparql_query

        # Update Solid mode settings
        session.solid_mode = context.solid_mode
        if context.catalog_id:
            session.catalog_id = context.catalog_id
        if context.catalog_url:
            session.catalog_url = context.catalog_url

        # Save results history
        if context.results_history:
            session.results_history_data = [entry.to_dict() for entry in context.results_history]

        # Save visualization history
        if context.visualization_history:
            session.visualization_history = [entry.to_dict() for entry in context.visualization_history]
            session.last_visualization_code = context.visualization_history[-1].code

        # Save calculation history
        if context.calculation_history:
            session.calculation_history = [entry.to_dict() for entry in context.calculation_history]
            session.last_calculation_code = context.last_calculation_code
            session.last_calculation_results = context.last_calculation_results

        # Save catalog search history
        if context.catalog_search_history:
            session.catalog_search_history = context.catalog_search_history

        # Update last activity timestamp
        from datetime import datetime, timezone
        session.last_activity = datetime.now(timezone.utc)

        # Save conversation messages as ChatSessionMessage entries
        from ..models import ChatSessionMessage
        messages_saved = 0

        if user_message:
            user_msg = ChatSessionMessage(
                session_id=context.session_id,
                message=user_message,
                is_user_message=True,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(user_msg)
            messages_saved += 1

        if assistant_message:
            assistant_msg = ChatSessionMessage(
                session_id=context.session_id,
                message=assistant_message,
                is_user_message=False,
                sparql_query=context.last_sparql_query,
                sparql_results={"results": {"bindings": context.last_sparql_results}} if context.last_sparql_results else None,
                timestamp=datetime.now(timezone.utc)
            )
            db.add(assistant_msg)
            messages_saved += 1

        db.add(session)
        db.commit()

        logger.info(f"[Agent Context] Saved context for session {context.session_id}:")
        logger.info(f"  - results_history: {len(context.results_history)} entries")
        logger.info(f"  - visualizations: {len(context.visualization_history)} entries")
        logger.info(f"  - calculations: {len(context.calculation_history)} entries")
        logger.info(f"  - catalog_search_history: {len(context.catalog_search_history)} entries")
        logger.info(f"  - conversation_messages: {messages_saved} new messages saved")
        logger.info(f"  - solid_mode: {context.solid_mode}")
        return True

    except Exception as e:
        logger.error(f"[Agent Context] Error saving context: {e}", exc_info=True)
        db.rollback()
        return False


# =============================================================================
# CREDENTIAL HANDOFF
#
# The chat stream is consumed with EventSource, which cannot set request
# headers, so anything it needs has to travel in the URL. Credentials in a URL
# end up in server logs, browser history and Referer headers, so the client
# hands them over in a POST first and passes only a short-lived opaque
# reference on the stream URL.
# =============================================================================
_TOKEN_HANDOFF_TTL_SECONDS = 120
_credential_handoff: dict[str, tuple[dict, datetime]] = {}


def _store_credentials(credentials: dict) -> str:
    """Store a credential bundle and return a short-lived reference to it."""
    _prune_credential_handoff()
    reference = uuid.uuid4().hex
    _credential_handoff[reference] = (credentials, datetime.now(timezone.utc))
    return reference


def _take_credentials(reference: Optional[str]) -> dict:
    """Resolve and consume a reference. Returns {} if unknown or expired."""
    _prune_credential_handoff()
    if not reference:
        return {}
    entry = _credential_handoff.pop(reference, None)
    return entry[0] if entry else {}


def _prune_credential_handoff() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_TOKEN_HANDOFF_TTL_SECONDS)
    for reference, (_, created) in list(_credential_handoff.items()):
        if created < cutoff:
            del _credential_handoff[reference]


def _api_key_from_header(x_llm_api_key: Optional[str]) -> Optional[str]:
    """Normalise the per-request API key header."""
    return x_llm_api_key.strip() if x_llm_api_key and x_llm_api_key.strip() else None


@router.post("/credentials", summary="Exchange credentials for a stream reference")
async def exchange_credentials(
    authorization: Optional[str] = Header(None),
    x_llm_api_key: Optional[str] = Header(None),
):
    """Take the credentials the chat stream will need.

    The Solid access token arrives in the Authorization header, the language
    model key in X-LLM-Api-Key. Both are optional: a deployment may configure
    the model key in its environment, and the dataspace may be readable without
    signing in. Returns a reference that expires quickly and is redeemed once.
    """
    credentials: dict = {}

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        credentials["solid_token"] = token.strip()

    api_key = _api_key_from_header(x_llm_api_key)
    if api_key:
        credentials["llm_api_key"] = api_key

    return {
        "credentials_ref": _store_credentials(credentials),
        "expires_in": _TOKEN_HANDOFF_TTL_SECONDS,
    }


@router.get("/profiles", summary="List the available language model profiles")
async def list_profiles(settings: AppSettings = Depends(get_settings)):
    """Describe the selectable models and which provider key each one needs.

    `configured` reports whether the server already holds a key for a provider,
    so the interface can show which ones the user still has to supply.
    """
    configured = {
        "deepseek": bool(settings.deepseek_api_key),
        "openai": bool(settings.openai_api_key),
        "fireworks": bool(settings.fireworks_api_key),
        "ollama": True,  # Runs locally, no credentials involved.
    }
    return {
        "profiles": describe_llm_profiles(),
        "configured_on_server": configured,
    }


@router.get("/chat", summary="Agent-orchestrated chat via SSE")
async def agent_chat(
    message: str = Query(..., description="User message/query"),
    user_for_data: str = Query(..., description="Workspace ID"),
    llm_profile: str = Query("deepseek_chat", description="LLM profile to use"),
    session_id: Optional[str] = Query(None, description="Existing session ID for context"),
    agentic_reasoning_enabled: bool = Query(False, description="Enable agentic reasoning"),
    internal_reasoning_enabled: bool = Query(False, description="Enable internal reasoning"),
    few_shot_prompting_enabled: bool = Query(False, description="Enable few-shot prompting"),
    interactive_mode: bool = Query(False, description="Enable interactive model selection"),
    auto_execute_plans: bool = Query(True, description="Auto-execute plans without confirmation"),
    request_timestamp: Optional[str] = Query(None, description="Request timestamp"),
    # Solid/Comunica integration parameters
    solid_mode: bool = Query(False, description="Enable Solid mode for external catalog"),
    catalog_id: str = Query("", description="External catalog ID"),
    catalog_url: str = Query("", description="External catalog API URL"),
    credentials_ref: Optional[str] = Query(None, description="Reference obtained from POST /credentials"),
    db: Session = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
):
    """
    Main endpoint for agent-orchestrated chat.

    The agent analyzes the user's intent and routes to the appropriate handler:
    - DATA_EXTRACTION: Forward to SPARQL pipeline for new data extraction
    - FOLLOW_UP_QUERY: Use existing session context for follow-up questions
    - CORPUS_INFO: Return information about available files without SPARQL
    - DATA_VISUALIZATION: Generate and execute matplotlib code for plots
    - NEW_QUERY: Detect context switch and start new session
    """
    credentials = _take_credentials(credentials_ref)
    solid_auth_token = credentials.get("solid_token")

    try:
        # Get LLM instance
        try:
            llm_instance = get_llm_for_profile(
                llm_profile, settings, api_key=credentials.get("llm_api_key")
            )
        except MissingApiKeyError as exc:
            # Answered as a normal error response rather than a stream, so the
            # interface can send the user straight to its settings.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "missing_api_key",
                    "provider": exc.provider,
                    "message": str(exc),
                },
            )
        if not llm_instance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid LLM profile: {llm_profile}"
            )

        # Get Redis client for caching
        redis_client = await get_redis_client()

        # Load context if session exists
        context = None
        if session_id:
            context = await load_agent_context(session_id, user_for_data, db, redis_client)
            if context:
                logger.info(f"[Agent Router] Loaded context for session {session_id}")
            else:
                logger.info(f"[Agent Router] No context found for session {session_id}, starting fresh")

        # Create agent
        agent = OrchestratingAgent(
            llm=llm_instance,
            workspace_id=user_for_data,
            context=context,
            llm_profile=llm_profile
        )

        # Set Solid/Comunica parameters in context
        # solid_mode enables authenticated catalog access - catalog_id/url are optional
        # (defaults from settings.catalog_api_url will be used if not provided)
        if solid_mode:
            agent.context.solid_mode = True
            if catalog_id:
                agent.context.catalog_id = catalog_id
            if catalog_url:
                agent.context.catalog_url = catalog_url
            if solid_auth_token:
                agent.context.solid_auth_token = solid_auth_token
                logger.info(f"[Agent Router] Solid mode enabled with auth token (using default catalog)")
            else:
                logger.info(f"[Agent Router] Solid mode enabled without auth token")

        # Generate request timestamp if not provided
        request_ts = request_timestamp or datetime.now(timezone.utc).isoformat()

        async def event_generator():
            """Generate SSE events from agent"""
            last_assistant_message = None
            try:
                async for event in agent.route_and_execute(
                    user_query=message,
                    db_session=db,
                    settings=settings,
                    agentic_reasoning_enabled=agentic_reasoning_enabled,
                    internal_reasoning_enabled=internal_reasoning_enabled,
                    few_shot_prompting_enabled=few_shot_prompting_enabled,
                    interactive_mode=interactive_mode,
                    auto_execute_plans=auto_execute_plans,
                    redis_client=redis_client
                ):
                    # If plan confirmation is required, store the plan for later
                    if isinstance(event, str) and "plan_confirmation_required" in event:
                        if agent.context and agent.context.current_plan:
                            plan = agent.context.current_plan
                            _pending_plans[plan.plan_id] = plan
                            logger.info(f"[Agent Router] Stored pending plan {plan.plan_id}")

                    # If Comunica execution is required, store the plan for resumption after frontend executes query
                    if isinstance(event, str) and "comunica_execution_required" in event:
                        if agent.context and agent.context.current_plan:
                            plan = agent.context.current_plan
                            # Extract session_id from the event
                            try:
                                event_data = json.loads(event.replace("data: ", "").strip())
                                event_session_id = event_data.get("session_id", agent.context.session_id or request_ts)
                            except (json.JSONDecodeError, AttributeError):
                                event_session_id = agent.context.session_id or request_ts
                            store_comunica_waiting_plan(event_session_id, plan)
                            logger.info(f"[Agent Router] Stored plan for Comunica execution, session: {event_session_id}")

                    # Track last assistant message for conversation history
                    if isinstance(event, str):
                        try:
                            import json
                            event_data = json.loads(event.replace("data: ", "").strip())
                            if isinstance(event_data, dict):
                                # Capture final result messages or summaries
                                if event_data.get("step_id") in ["final_result", "sparql_execution_completed", "follow_up_completed"]:
                                    last_assistant_message = event_data.get("message", "")
                                elif event_data.get("summary"):
                                    last_assistant_message = event_data.get("summary", "")
                        except (json.JSONDecodeError, AttributeError):
                            pass

                    yield event

                # Save agent context with conversation history
                if agent.context:
                    # Create session if needed (e.g., for catalog search caching)
                    if not agent.context.session_id and agent.context.catalog_search_history:
                        # Create a new session to persist catalog search cache
                        new_session = ChatSession(
                            id=request_ts,
                            workspace_id=user_for_data,
                            initial_query=message,
                            selected_models=agent.context.last_data_sources or [],
                            model_info_blocks=agent.context.model_info_blocks or "",
                            model_check_hints=agent.context.model_check_hints or "",
                            solid_mode=agent.context.solid_mode,
                            catalog_id=agent.context.catalog_id,
                            catalog_url=agent.context.catalog_url
                        )
                        db.add(new_session)
                        db.commit()
                        agent.context.session_id = request_ts
                        logger.info(f"[Agent Router] Created session {request_ts} for catalog search caching")

                    if agent.context.session_id:
                        await save_agent_context(
                            context=agent.context,
                            db=db,
                            user_message=message,
                            assistant_message=last_assistant_message
                        )
                        logger.info(f"[Agent Router] Saved conversation to session {agent.context.session_id}")

                # Send end stream event with session_id for frontend to store
                from ..utils import format_sse_event
                yield await format_sse_event(
                    data={
                        "message": "Agent Pipeline beendet",
                        "step_id": "agent_ended",
                        "session_id": agent.context.session_id if agent.context else None
                    },
                    event_type="end_stream"
                )

            except Exception as e:
                logger.error(f"[Agent Router] Error in event generator: {e}", exc_info=True)
                from ..utils import format_sse_event
                yield await format_sse_event({
                    "message": f"Agent-Fehler: {str(e)}",
                    "step_id": "agent_error",
                    "is_error": True,
                    "request_timestamp": request_ts
                }, "pipeline_error")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agent Router] Error processing request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}"
        )


@router.get("/context/{session_id}", summary="Get agent context for a session")
async def get_agent_context(
    session_id: str,
    workspace_id: str = Query(..., alias="user_for_data"),
    db: Session = Depends(get_session)
):
    """
    Retrieve the current agent context for a session.
    Useful for debugging and understanding agent state.
    """
    context = await load_agent_context(session_id, workspace_id, db)

    if not context:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No context found for session {session_id}"
        )

    return {
        "session_id": context.session_id,
        "workspace_id": context.workspace_id,
        "last_data_sources": context.last_data_sources,
        "has_sparql_results": context.last_sparql_results is not None,
        "result_count": len(context.last_sparql_results) if context.last_sparql_results else 0,
        "last_query": context.last_user_query,
        "has_model_info": context.model_info_blocks is not None
    }


@router.post("/reset-context", summary="Reset agent context")
async def reset_agent_context(
    session_id: Optional[str] = Query(None),
    workspace_id: str = Query(..., alias="user_for_data")
):
    """
    Reset the agent context, optionally for a specific session.
    This is useful when the user wants to start completely fresh.
    """
    # Context is managed per-request in this implementation
    # This endpoint mainly serves as a signal to the frontend
    return {
        "status": "success",
        "message": "Context reset signal sent. Next request will start fresh.",
        "session_id": session_id,
        "workspace_id": workspace_id
    }


# Store pending plans for confirmation (in-memory for simplicity)
_pending_plans: dict = {}


@router.post("/confirm-plan", summary="Confirm and execute a pending plan")
async def confirm_plan(
    plan_id: str = Query(..., description="Plan ID to confirm"),
    user_for_data: str = Query(..., description="Workspace ID"),
    llm_profile: str = Query("deepseek_chat", description="LLM profile to use"),
    session_id: Optional[str] = Query(None, description="Existing session ID for context"),
    agentic_reasoning_enabled: bool = Query(False, description="Enable agentic reasoning"),
    internal_reasoning_enabled: bool = Query(False, description="Enable internal reasoning"),
    few_shot_prompting_enabled: bool = Query(False, description="Enable few-shot prompting"),
    interactive_mode: bool = Query(False, description="Enable interactive model selection"),
    db: Session = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
    x_llm_api_key: Optional[str] = Header(None),
):
    """
    Confirm and execute a previously generated plan that was awaiting confirmation.
    This is called when auto_execute_plans is False and the user confirms the plan.
    """
    try:
        # Get LLM instance
        llm_instance = get_llm_for_profile(
            llm_profile, settings, api_key=_api_key_from_header(x_llm_api_key)
        )
        if not llm_instance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid LLM profile: {llm_profile}"
            )

        # Load context if session exists
        context = None
        if session_id:
            context = await load_agent_context(session_id, user_for_data, db)

        # Check if we have a pending plan
        if plan_id not in _pending_plans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No pending plan found with ID {plan_id}"
            )

        pending_plan = _pending_plans.pop(plan_id)

        # Create agent with context
        agent = OrchestratingAgent(
            llm=llm_instance,
            workspace_id=user_for_data,
            context=context,
            llm_profile=llm_profile
        )

        # Restore the plan to context
        if context:
            context.current_plan = pending_plan

        async def event_generator():
            """Generate SSE events from plan execution"""
            try:
                async for event in agent.execute_plan(
                    plan=pending_plan,
                    db_session=db,
                    settings=settings,
                    agentic_reasoning_enabled=agentic_reasoning_enabled,
                    internal_reasoning_enabled=internal_reasoning_enabled,
                    few_shot_prompting_enabled=few_shot_prompting_enabled,
                    interactive_mode=interactive_mode
                ):
                    yield event

                # Send end stream event
                from ..utils import format_sse_event
                yield await format_sse_event(
                    data={"message": "Plan-Ausführung beendet", "step_id": "plan_execution_ended"},
                    event_type="end_stream"
                )

            except Exception as e:
                logger.error(f"[Agent Router] Error in plan execution: {e}", exc_info=True)
                from ..utils import format_sse_event
                yield await format_sse_event({
                    "message": f"Plan-Ausführungsfehler: {str(e)}",
                    "step_id": "plan_execution_error",
                    "is_error": True
                }, "pipeline_error")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agent Router] Error confirming plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan confirmation error: {str(e)}"
        )


@router.post("/cancel-plan", summary="Cancel a pending plan")
async def cancel_plan(
    plan_id: str = Query(..., description="Plan ID to cancel")
):
    """
    Cancel a pending plan that was awaiting confirmation.
    """
    if plan_id in _pending_plans:
        del _pending_plans[plan_id]
        return {"status": "success", "message": f"Plan {plan_id} cancelled"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending plan found with ID {plan_id}"
        )


# Store plans awaiting Comunica results from frontend
_comunica_waiting_plans: dict = {}


@router.post("/comunica-results", summary="Receive Comunica query results from frontend")
async def receive_comunica_results(
    request: ComunicaResultsRequest,
    db: Session = Depends(get_session)
):
    """
    Receive SPARQL query results from frontend after Comunica execution.
    Stores results in the agent context for further processing AND persists to database.

    This endpoint is called by the frontend after it executes a SPARQL query
    via Comunica against an external Solid catalog.
    """
    try:
        redis_client = await get_redis_client()

        # Check if we have a waiting plan for this session
        if request.session_id not in _comunica_waiting_plans:
            logger.warning(f"[Agent Router] No waiting plan found for session {request.session_id}")
            # Create a new entry to store results
            _comunica_waiting_plans[request.session_id] = {
                "results": request.results,
                "variables": request.variables,
                "total": request.total,
                "step_number": request.step_number,
                "received_at": datetime.now(timezone.utc).isoformat()
            }
        else:
            # Update existing entry with results
            _comunica_waiting_plans[request.session_id].update({
                "results": request.results,
                "variables": request.variables,
                "total": request.total,
                "step_number": request.step_number,
                "received_at": datetime.now(timezone.utc).isoformat()
            })

        # === NEW: Persist Comunica results to database ===
        # This is critical for follow-up queries to have access to the data
        session = db.exec(
            select(ChatSession).where(ChatSession.id == request.session_id)
        ).first()

        # If session doesn't exist, create it (for Solid mode where session is generated on-the-fly)
        if not session and request.workspace_id:
            logger.info(f"[Agent Router] Creating new ChatSession for Solid mode: {request.session_id}")
            session = ChatSession(
                id=request.session_id,
                workspace_id=request.workspace_id,
                initial_query=request.user_query or "Comunica Query",
                selected_models=[],
                model_info_blocks="Solid/Comunica Mode",
                model_check_hints="External catalog query",
                solid_mode=True,
                catalog_id=request.catalog_id,
                catalog_url=request.catalog_url
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info(f"[Agent Router] Created ChatSession {request.session_id} for workspace {request.workspace_id}")

        if session:
            # Update SPARQL results in session
            session.last_sparql_results = request.results
            session.last_sparql_variables = request.variables
            if request.sparql_query:
                session.last_sparql_query = request.sparql_query

            # Add to results history
            results_history = session.results_history_data or []
            new_entry = {
                "entry_id": f"result_{len(results_history) + 1}",
                "step_number": request.step_number,
                "user_query": request.user_query or "Comunica Query",
                "description": f"Comunica-Ergebnisse: {request.total} Datensätze",
                "variables": request.variables,
                "total_count": request.total,
                "sample": request.results[:10] if request.results else [],
                "data_sources": ["Solid Catalog (Comunica)"],
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            results_history.append(new_entry)
            session.results_history_data = results_history

            # Update Solid mode settings
            if request.catalog_id:
                session.solid_mode = True
                session.catalog_id = request.catalog_id
            if request.catalog_url:
                session.catalog_url = request.catalog_url

            # Update timestamp
            session.last_activity = datetime.now(timezone.utc)

            db.add(session)
            db.commit()
            logger.info(f"[Agent Router] Persisted Comunica results to session {request.session_id}")
        else:
            logger.warning(f"[Agent Router] Session {request.session_id} not found and no workspace_id provided - results not persisted")

        # Check if there are more steps pending
        plan_data = _comunica_waiting_plans.get(request.session_id, {})
        plan = plan_data.get("plan")
        has_more_steps = False

        if plan:
            # Check for pending steps after the current one
            has_more_steps = any(
                s.status == "pending" and s.step_number > request.step_number
                for s in plan.steps
            )

        logger.info(
            f"[Agent Router] Received Comunica results for session {request.session_id}: "
            f"{request.total} results, {len(request.variables)} variables, "
            f"step {request.step_number}, has_more_steps={has_more_steps}"
        )

        return {
            "status": "ok",
            "message": f"Received {request.total} results",
            "has_more_steps": has_more_steps,
            "session_id": request.session_id,
            "persisted": session is not None
        }

    except Exception as e:
        logger.error(f"[Agent Router] Error receiving Comunica results: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error receiving Comunica results: {str(e)}"
        )


async def plan_query_refinement(context, results, plan_data, llm_instance, session_id):
    """Decide whether an empty result deserves another attempt, and prepare it.

    Two rounds are possible, neither visible in the conversation:

    1. The failed query is read for the properties it filtered on, and a probe
       asks which literals those properties actually hold.
    2. Armed with those values the query is written again, filtering on terms
       that exist.

    Returns None when the results are usable, when nothing suggests a fix, or
    when the budget is spent - in each case the caller reports what it has.
    """
    from ..query_refinement import (
        MAX_QUERY_REFINEMENTS,
        build_retry_instruction,
        build_value_probe_query,
        extract_filtered_properties,
        prefixes_of,
        summarise_observed_values,
    )
    from ..sparql_generation import generate_sparql_query

    def comunica_event(query):
        return {
            "sparql_query": query,
            "dataset_urls": context.last_dataset_urls,
            "session_id": session_id,
            "user_query": context.last_user_query,
        }

    # Second round: a probe has answered, so rewrite the original query.
    if plan_data.get("probe_for_query"):
        failed_query = plan_data["probe_for_query"]
        observed = summarise_observed_values(results)
        logger.info(f"[Refine] Values observed for {list(observed)}")

        if not observed:
            return None

        instruction = build_retry_instruction(observed, failed_query)
        try:
            retry = await generate_sparql_query(
                user_query=f"{context.last_user_query}\n\n{instruction}",
                model_info_blocks=context.model_info_blocks or "",
                llm_instance=llm_instance,
                request_id="query_refinement",
            )
        except Exception as exc:
            logger.warning(f"[Refine] Could not rewrite the query: {exc}")
            return None

        new_query = retry.get("sparql_query") if isinstance(retry, dict) else None
        if not new_query or new_query.strip() == failed_query.strip():
            return None

        context.last_sparql_query = new_query
        return {
            "waiting_state": {"probe_for_query": None, "results": [], "variables": []},
            "status_event": {
                "message": "Refining the query against the values found in the data...",
                "step_id": "query_refinement",
            },
            "comunica_event": comunica_event(new_query),
        }

    # First round: only an empty result is worth investigating.
    if results or not context.last_dataset_urls:
        return None
    if context.query_attempts >= MAX_QUERY_REFINEMENTS:
        logger.info("[Refine] Budget spent, reporting the empty result")
        return None

    failed_query = context.last_sparql_query or ""
    properties = extract_filtered_properties(failed_query)
    if not properties:
        # Nothing was filtered, so the data genuinely holds no answer.
        return None

    probe = build_value_probe_query(properties, prefixes_of(failed_query))
    if not probe:
        return None

    context.query_attempts += 1
    logger.info(f"[Refine] Empty result, probing values of {properties}")

    return {
        "waiting_state": {"probe_for_query": failed_query, "results": [], "variables": []},
        "status_event": {
            "message": "No matches yet - checking which values the data contains...",
            "step_id": "query_probe",
        },
        "comunica_event": comunica_event(probe),
    }


@router.get("/continue-plan", summary="Continue agent plan after Comunica execution")
async def continue_plan_after_comunica(
    session_id: str = Query(..., description="Session ID"),
    user_for_data: str = Query(..., description="Workspace ID"),
    llm_profile: str = Query("deepseek_chat", description="LLM profile to use"),
    agentic_reasoning_enabled: bool = Query(False, description="Enable agentic reasoning"),
    internal_reasoning_enabled: bool = Query(False, description="Enable internal reasoning"),
    few_shot_prompting_enabled: bool = Query(False, description="Enable few-shot prompting"),
    interactive_mode: bool = Query(False, description="Enable interactive model selection"),
    db: Session = Depends(get_session),
    settings: AppSettings = Depends(get_settings),
    x_llm_api_key: Optional[str] = Header(None),
):
    """
    Continue an agent plan after the frontend has executed a Comunica query.
    This endpoint is called to resume plan execution with the received results.
    """
    try:
        # Get LLM instance
        llm_instance = get_llm_for_profile(
            llm_profile, settings, api_key=_api_key_from_header(x_llm_api_key)
        )
        if not llm_instance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid LLM profile: {llm_profile}"
            )

        # Check if we have stored results and plan for this session
        if session_id not in _comunica_waiting_plans:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No waiting plan or results found for session {session_id}"
            )

        plan_data = _comunica_waiting_plans[session_id]
        results = plan_data.get("results", [])
        variables = plan_data.get("variables", [])
        plan = plan_data.get("plan")

        # Get Redis client
        redis_client = await get_redis_client()

        # Load context
        context = await load_agent_context(session_id, user_for_data, db, redis_client)
        if not context:
            context = AgentContext(workspace_id=user_for_data)
            context.session_id = session_id

        # Store Comunica results in context
        context.last_sparql_results = results
        context.last_sparql_variables = variables

        # An empty result is often a filter on a value the data spells
        # differently, so look at what is actually there and try again before
        # reporting back. Both rounds stay between here and the browser.
        refinement = await plan_query_refinement(
            context=context,
            results=results,
            plan_data=plan_data,
            llm_instance=llm_instance,
            session_id=session_id,
        )
        if refinement:
            _comunica_waiting_plans[session_id].update(refinement["waiting_state"])

            async def refine_generator():
                from ..utils import format_sse_event

                yield await format_sse_event(refinement["status_event"], "pipeline_update")
                yield await format_sse_event(
                    refinement["comunica_event"], "comunica_execution_required"
                )

            return StreamingResponse(refine_generator(), media_type="text/event-stream")

        # Also add to results_history so that steps using "latest" can find them
        if results:
            original_query = plan.original_query if plan else "Comunica Query"
            context.add_to_results_history(
                user_query=original_query,
                results=results,
                variables=variables,
                data_sources=["Solid Catalog (Comunica)"],
                description=f"Comunica-Ergebnisse: {len(results)} Datensätze"
            )
            logger.info(f"[Agent Router] Added {len(results)} Comunica results to results_history")

        # If we have a cached plan, restore it
        if plan:
            context.current_plan = plan
            # Mark the awaiting step as completed
            for step in plan.steps:
                if step.status == "awaiting_comunica":
                    step.status = "completed"
                    step.result = {"total": len(results), "variables": variables}
                    break

        # Create agent
        agent = OrchestratingAgent(
            llm=llm_instance,
            workspace_id=user_for_data,
            context=context,
            llm_profile=llm_profile
        )

        async def event_generator():
            """Generate SSE events from plan continuation"""
            try:
                # If we have a plan with pending steps, continue execution
                if context.current_plan:
                    async for event in agent.continue_plan_execution(
                        db_session=db,
                        settings=settings,
                        agentic_reasoning_enabled=agentic_reasoning_enabled,
                        internal_reasoning_enabled=internal_reasoning_enabled,
                        few_shot_prompting_enabled=few_shot_prompting_enabled,
                        interactive_mode=interactive_mode,
                        redis_client=redis_client
                    ):
                        yield event
                else:
                    # No plan, just send completion
                    from ..utils import format_sse_event
                    yield await format_sse_event({
                        "message": "Comunica-Ergebnisse empfangen",
                        "step_id": "comunica_results_received",
                        "total_results": len(results)
                    }, "pipeline_update")

                # Send end stream event
                from ..utils import format_sse_event
                yield await format_sse_event(
                    data={"message": "Plan-Fortsetzung beendet", "step_id": "plan_continuation_ended"},
                    event_type="end_stream"
                )

                # Clean up stored data
                if session_id in _comunica_waiting_plans:
                    del _comunica_waiting_plans[session_id]

            except Exception as e:
                logger.error(f"[Agent Router] Error in plan continuation: {e}", exc_info=True)
                from ..utils import format_sse_event
                yield await format_sse_event({
                    "message": f"Fehler bei Plan-Fortsetzung: {str(e)}",
                    "step_id": "continuation_error",
                    "is_error": True
                }, "pipeline_error")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Agent Router] Error continuing plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plan continuation error: {str(e)}"
        )


def store_comunica_waiting_plan(session_id: str, plan) -> None:
    """Store a plan that is waiting for Comunica results from frontend."""
    if session_id not in _comunica_waiting_plans:
        _comunica_waiting_plans[session_id] = {}
    _comunica_waiting_plans[session_id]["plan"] = plan
    logger.info(f"[Agent Router] Stored plan awaiting Comunica results for session {session_id}")
