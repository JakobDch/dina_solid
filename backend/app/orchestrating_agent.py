"""
Orchestrating Agent for DINa ESG Reporting

This module provides an agent that classifies user intents and routes requests
to the appropriate handlers (extraction, follow-up, corpus info, visualization).
"""

import json
import logging
import re
import asyncio
import uuid
import io
import os
import base64
import httpx
from enum import Enum
from typing import AsyncGenerator, Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .llm_services import OllamaLLM, DeepSeekLLM, OpenAILLM
from .utils import format_sse_event

logger = logging.getLogger(__name__)


class AgentIntent(Enum):
    """Classification of user intents for routing"""
    DATA_EXTRACTION = "data_extraction"      # New data extraction via SPARQL pipeline
    FOLLOW_UP_QUERY = "follow_up_query"      # Follow-up to existing session
    CORPUS_INFO = "corpus_info"              # Information about available files
    DATA_VISUALIZATION = "data_visualization" # Generate plots from results
    DATA_CALCULATION = "data_calculation"    # Calculations/aggregations on extracted data
    NEW_QUERY = "new_query"                  # User wants different data sources


class StepCondition(Enum):
    """Conditions for conditional step execution"""
    ALWAYS = "always"                        # Always execute
    PREVIOUS_SUCCESS = "previous_success"    # Only if previous step succeeded
    PREVIOUS_FAILED = "previous_failed"      # Only if previous step failed
    HAS_RESULTS = "has_results"              # Only if there are results available
    NO_RESULTS = "no_results"                # Only if no results were found


@dataclass
class ExecutionStep:
    """A single step in an execution plan"""
    step_number: int
    intent: AgentIntent
    sub_query: str
    depends_on: Optional[int] = None
    result: Optional[Any] = None
    status: str = "pending"  # pending, running, completed, failed, skipped, awaiting_clarification
    condition: Optional[StepCondition] = None
    fallback_step: Optional[int] = None
    error_message: Optional[str] = None
    # Clarification state - stores data needed to resume after user answers
    clarification_data: Optional[Dict[str, Any]] = None
    # Reference to specific results from history (e.g., "result_1", "latest")
    uses_result: Optional[str] = None


@dataclass
class ExecutionPlan:
    """A complete execution plan for a user query"""
    original_query: str
    steps: List['ExecutionStep'] = field(default_factory=list)
    current_step: int = 0
    summary_required: bool = True
    awaiting_confirmation: bool = False
    awaiting_clarification: bool = False  # True when waiting for user to answer a clarification question
    plan_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert plan to dictionary for SSE events"""
        return {
            "plan_id": self.plan_id,
            "original_query": self.original_query,
            "steps": [
                {
                    "step_number": s.step_number,
                    "intent": s.intent.value,
                    "sub_query": s.sub_query,
                    "depends_on": s.depends_on,
                    "status": s.status,
                    "condition": s.condition.value if s.condition else None,
                    "fallback_step": s.fallback_step,
                    "clarification_data": s.clarification_data,
                    "uses_result": s.uses_result
                }
                for s in self.steps
            ],
            "current_step": self.current_step,
            "summary_required": self.summary_required,
            "awaiting_clarification": self.awaiting_clarification
        }


# Context management constants
MAX_SPARQL_RESULTS_IN_CONTEXT = 100  # Results above this threshold are cached
MAX_CONVERSATION_HISTORY = 10  # Sliding window for conversation history

RESULTS_CACHE_TTL = 3600  # 1 hour TTL for cached results


@dataclass
class ResultsReference:
    """
    Lightweight reference to cached SPARQL results.
    Instead of keeping large result sets in context, we store them in Redis
    and keep only this reference with metadata and a sample.
    """
    cache_key: str
    total_count: int
    variables: List[str]
    sample: List[Dict]  # First 5 rows for LLM context
    cached_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "cache_key": self.cache_key,
            "total_count": self.total_count,
            "variables": self.variables,
            "sample": self.sample,
            "cached_at": self.cached_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResultsReference':
        """Create from dictionary"""
        return cls(
            cache_key=data["cache_key"],
            total_count=data["total_count"],
            variables=data["variables"],
            sample=data["sample"],
            cached_at=data.get("cached_at", datetime.now(timezone.utc).isoformat())
        )


@dataclass
class ResultsHistoryEntry:
    """
    Entry in the results history tracking all extractions in a session.
    Allows the agent to reference any previous result set by ID.
    """
    entry_id: str  # Unique ID for this entry (e.g., "result_1", "result_2")
    step_number: Optional[int]  # Which plan step created this (if applicable)
    user_query: str  # The query that produced these results
    description: str  # Short description of what was extracted
    variables: List[str]  # Column names
    total_count: int  # Number of rows
    sample: List[Dict]  # First 5-10 rows for context
    data_sources: List[str]  # Which files were queried
    sparql_query: Optional[str] = None  # The SPARQL query used
    cache_key: Optional[str] = None  # Redis cache key for full data (if cached)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "step_number": self.step_number,
            "user_query": self.user_query,
            "description": self.description,
            "variables": self.variables,
            "total_count": self.total_count,
            "sample": self.sample,
            "data_sources": self.data_sources,
            "sparql_query": self.sparql_query,
            "cache_key": self.cache_key,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResultsHistoryEntry':
        return cls(
            entry_id=data["entry_id"],
            step_number=data.get("step_number"),
            user_query=data["user_query"],
            description=data["description"],
            variables=data["variables"],
            total_count=data["total_count"],
            sample=data["sample"],
            data_sources=data["data_sources"],
            sparql_query=data.get("sparql_query"),
            cache_key=data.get("cache_key"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat())
        )

    def get_summary_for_llm(self) -> str:
        """Short summary for LLM context when listing available results"""
        return (
            f"[{self.entry_id}] {self.description} - "
            f"{self.total_count} rows, columns: {', '.join(self.variables[:5])}"
            f"{'...' if len(self.variables) > 5 else ''}"
        )


@dataclass
class ResultsRequest:
    """
    Agent's request to access specific results from history.
    Used during plan generation to specify which data the agent needs.
    """
    entry_id: str  # Which result set to access (e.g., "result_1", "latest")
    reason: str  # Why the agent needs this data
    max_rows: Optional[int] = None  # Limit rows if specified (for LLM context)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "reason": self.reason,
            "max_rows": self.max_rows
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResultsRequest':
        return cls(
            entry_id=data["entry_id"],
            reason=data["reason"],
            max_rows=data.get("max_rows")
        )


@dataclass
class VisualizationHistoryEntry:
    """
    Entry tracking a visualization created in this session.
    """
    entry_id: str  # Unique ID (e.g., "viz_1")
    description: str  # What was visualized
    chart_type: str  # "bar", "line", "pie", etc.
    code: str  # The matplotlib/plotly code
    data_source_id: Optional[str] = None  # Which result set was visualized
    image_path: Optional[str] = None  # Path to saved image if any
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "description": self.description,
            "chart_type": self.chart_type,
            "code": self.code,
            "data_source_id": self.data_source_id,
            "image_path": self.image_path,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisualizationHistoryEntry':
        return cls(
            entry_id=data["entry_id"],
            description=data["description"],
            chart_type=data.get("chart_type", "unknown"),
            code=data["code"],
            data_source_id=data.get("data_source_id"),
            image_path=data.get("image_path"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat())
        )

    def get_summary_for_llm(self) -> str:
        """Short summary for LLM context"""
        return f"[{self.entry_id}] {self.chart_type} chart: {self.description}"


@dataclass
class CalculationHistoryEntry:
    """
    Entry tracking a calculation performed in this session.
    """
    entry_id: str  # Unique ID (e.g., "calc_1")
    description: str  # What was calculated
    code: str  # The Python code
    result_summary: str  # Human-readable result summary
    result_data: Optional[Dict[str, Any]] = None  # Structured result data
    data_source_id: Optional[str] = None  # Which result set was used
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "description": self.description,
            "code": self.code,
            "result_summary": self.result_summary,
            "result_data": self.result_data,
            "data_source_id": self.data_source_id,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalculationHistoryEntry':
        return cls(
            entry_id=data["entry_id"],
            description=data["description"],
            code=data["code"],
            result_summary=data["result_summary"],
            result_data=data.get("result_data"),
            data_source_id=data.get("data_source_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat())
        )

    def get_summary_for_llm(self) -> str:
        """Short summary for LLM context"""
        return f"[{self.entry_id}] Calculation: {self.description} -> {self.result_summary}"


@dataclass
class AgentContext:
    """Maintains conversation context across interactions"""
    workspace_id: str
    session_id: Optional[str] = None
    last_data_sources: List[str] = field(default_factory=list)
    last_sparql_results: Optional[List[Dict]] = None  # Direct results (small sets)
    last_sparql_query: Optional[str] = None
    last_sparql_variables: Optional[List[str]] = None
    last_user_query: Optional[str] = None
    model_info_blocks: Optional[str] = None
    model_check_hints: Optional[str] = None
    conversation_history: List[Dict] = field(default_factory=list)
    # For plan-based execution
    current_plan: Optional['ExecutionPlan'] = None
    step_results: Dict[int, Any] = field(default_factory=dict)
    # For cached large results
    results_ref: Optional['ResultsReference'] = None
    _redis_client: Optional[Any] = field(default=None, repr=False)  # Redis client for lazy loading
    # Results history - tracks all extractions in this session
    results_history: List['ResultsHistoryEntry'] = field(default_factory=list)
    # For calculation results (chaining with visualization)
    last_calculation_results: Optional[Dict[str, Any]] = None
    last_calculation_code: Optional[str] = None
    _results_counter: int = field(default=0, repr=False)  # Counter for generating entry IDs
    # Solid/Comunica integration fields
    solid_mode: bool = False  # True when using external catalog via Solid
    catalog_id: str = ""  # External catalog ID
    catalog_url: str = ""  # External catalog API URL
    solid_auth_token: Optional[str] = None  # Solid OIDC access token for authenticated catalog API requests
    last_dataset_urls: List[Dict[str, str]] = field(default_factory=list)  # Dataset URLs for Comunica execution
    exploration_summary: str = ""  # What the agent concluded while working out the query
    exploration_step_count: int = 0  # Queries it ran to get there
    # === NEW: Visualization and Calculation History ===
    visualization_history: List['VisualizationHistoryEntry'] = field(default_factory=list)
    calculation_history: List['CalculationHistoryEntry'] = field(default_factory=list)
    _viz_counter: int = field(default=0, repr=False)
    _calc_counter: int = field(default=0, repr=False)
    # === Catalog Model Cache - persists fetched models across queries ===
    fetched_models_cache: Dict[str, str] = field(default_factory=dict)  # model_id -> content
    fetched_models_metadata: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # model_id -> metadata (title, classes, etc.)
    # === Catalog Search History - caches previous catalog searches in this session ===
    catalog_search_history: List[Dict[str, Any]] = field(default_factory=list)
    # === Catalog Index Cache - avoids reloading 55 catalog entries every request ===
    catalog_entries_cache: List[Any] = field(default_factory=list)

    def set_redis_client(self, redis_client):
        """Set Redis client for lazy loading of cached results"""
        self._redis_client = redis_client

    def add_to_results_history(
        self,
        user_query: str,
        description: str,
        results: List[Dict],
        variables: List[str],
        data_sources: List[str],
        sparql_query: Optional[str] = None,
        cache_key: Optional[str] = None,
        step_number: Optional[int] = None
    ) -> ResultsHistoryEntry:
        """
        Add a new result set to the history.
        Returns the created entry for reference.
        """
        self._results_counter += 1
        entry_id = f"result_{self._results_counter}"

        # Create sample (first 5-10 rows)
        sample_size = min(10, len(results))
        sample = results[:sample_size] if results else []

        entry = ResultsHistoryEntry(
            entry_id=entry_id,
            step_number=step_number,
            user_query=user_query,
            description=description,
            variables=variables,
            total_count=len(results),
            sample=sample,
            data_sources=data_sources,
            sparql_query=sparql_query,
            cache_key=cache_key
        )

        self.results_history.append(entry)
        logger.info(f"[AgentContext] Added {entry_id} to results history: {description} ({len(results)} rows)")
        return entry

    def get_results_history_summary(self) -> str:
        """
        Get a summary of all available results for LLM context.
        Used to help the agent decide which results to reference.
        """
        if not self.results_history:
            return "No earlier results are available."

        summaries = [entry.get_summary_for_llm() for entry in self.results_history]
        return "Available results:\n" + "\n".join(summaries)

    def add_visualization(
        self,
        description: str,
        chart_type: str,
        code: str,
        data_source_id: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> VisualizationHistoryEntry:
        """Add a visualization to the history."""
        self._viz_counter += 1
        entry_id = f"viz_{self._viz_counter}"

        entry = VisualizationHistoryEntry(
            entry_id=entry_id,
            description=description,
            chart_type=chart_type,
            code=code,
            data_source_id=data_source_id,
            image_path=image_path
        )
        self.visualization_history.append(entry)
        logger.info(f"[AgentContext] Added {entry_id} to visualization history: {description}")
        return entry

    def add_calculation(
        self,
        description: str,
        code: str,
        result_summary: str,
        result_data: Optional[Dict[str, Any]] = None,
        data_source_id: Optional[str] = None
    ) -> CalculationHistoryEntry:
        """Add a calculation to the history."""
        self._calc_counter += 1
        entry_id = f"calc_{self._calc_counter}"

        entry = CalculationHistoryEntry(
            entry_id=entry_id,
            description=description,
            code=code,
            result_summary=result_summary,
            result_data=result_data,
            data_source_id=data_source_id
        )
        self.calculation_history.append(entry)
        # Also update last_calculation for immediate access
        self.last_calculation_code = code
        self.last_calculation_results = result_data
        logger.info(f"[AgentContext] Added {entry_id} to calculation history: {description}")
        return entry

    def get_visualization_by_id(self, entry_id: str) -> Optional['VisualizationHistoryEntry']:
        """Get a specific visualization by ID"""
        if entry_id == "latest" and self.visualization_history:
            return self.visualization_history[-1]
        for entry in self.visualization_history:
            if entry.entry_id == entry_id:
                return entry
        return None

    def get_calculation_by_id(self, entry_id: str) -> Optional['CalculationHistoryEntry']:
        """Get a specific calculation by ID"""
        if entry_id == "latest" and self.calculation_history:
            return self.calculation_history[-1]
        for entry in self.calculation_history:
            if entry.entry_id == entry_id:
                return entry
        return None

    def get_full_context_summary(self) -> str:
        """
        Get a comprehensive summary of the entire session context for the LLM.
        This provides the agent with an overview without loading all data into context.
        The agent can then request specific data it needs via lazy loading.
        """
        parts = []

        # Session info
        parts.append("=== SESSION CONTEXT ===")
        parts.append(f"Session ID: {self.session_id or 'new session'}")
        parts.append(f"Workspace: {self.workspace_id}")
        parts.append(
            f"Signed in: {'yes' if self.solid_auth_token else 'no (public data only)'}"
        )

        # Data extractions summary
        parts.append("\n=== EXTRACTED DATA ===")
        if self.results_history:
            for entry in self.results_history:
                parts.append(entry.get_summary_for_llm())
        else:
            parts.append("No data has been extracted.")

        # Visualizations summary
        parts.append("\n=== CHARTS CREATED ===")
        if self.visualization_history:
            for entry in self.visualization_history:
                parts.append(entry.get_summary_for_llm())
        else:
            parts.append("No charts have been created.")

        # Calculations summary
        parts.append("\n=== CALCULATIONS PERFORMED ===")
        if self.calculation_history:
            for entry in self.calculation_history:
                parts.append(entry.get_summary_for_llm())
        else:
            parts.append("No calculations have been performed.")

        # Recent conversation (last 3 exchanges)
        parts.append("\n=== RECENT CONVERSATION ===")
        if self.conversation_history:
            recent = self.conversation_history[-6:]  # Last 3 exchanges (user + assistant)
            for msg in recent:
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:200]  # Truncate long messages
                if len(msg.get("content", "")) > 200:
                    content += "..."
                parts.append(f"{role}: {content}")
        else:
            parts.append("Nothing has been said yet.")

        parts.append("\n=== WHAT YOU CAN DO ===")
        parts.append("Any dataset can be reached by its ID (e.g. 'result_1', 'viz_1', 'calc_1').")
        parts.append("For follow-up requests, work from the data you already have instead of extracting it again.")

        return "\n".join(parts)

    def has_any_context(self) -> bool:
        """Check if there is any meaningful context from previous interactions."""
        return bool(
            self.results_history or
            self.visualization_history or
            self.calculation_history or
            self.last_sparql_results or
            self.conversation_history
        )

    def get_result_by_id(self, entry_id: str) -> Optional['ResultsHistoryEntry']:
        """Get a specific result entry by ID"""
        if entry_id == "latest" and self.results_history:
            return self.results_history[-1]

        for entry in self.results_history:
            if entry.entry_id == entry_id:
                return entry
        return None

    async def get_full_results_by_id(self, entry_id: str) -> Optional[List[Dict]]:
        """
        Get full results for a specific entry ID.
        Loads from cache if necessary.
        """
        entry = self.get_result_by_id(entry_id)
        if not entry:
            logger.warning(f"[AgentContext] Result entry not found: {entry_id}")
            return None

        # If it's a small set, the sample might be the full data
        if entry.total_count <= len(entry.sample):
            return entry.sample

        # Otherwise, try to load from cache
        if entry.cache_key and self._redis_client:
            try:
                cached_data = await self._redis_client.get(entry.cache_key)
                if cached_data:
                    return json.loads(cached_data)
                else:
                    logger.warning(f"Cached results not found for key: {entry.cache_key}")
            except Exception as e:
                logger.error(f"Error loading cached results for {entry_id}: {e}")

        # Fallback: return sample if cache not available
        logger.warning(f"[AgentContext] Full results not available for {entry_id}, returning sample")
        return entry.sample

    async def get_full_results(self, entry_id: Optional[str] = None) -> Optional[List[Dict]]:
        """
        Lazy load full results from cache or return direct results.
        If entry_id is provided, get specific results from history.
        Otherwise, get the latest/current results.
        """
        # If a specific entry is requested, use the history
        if entry_id:
            return await self.get_full_results_by_id(entry_id)

        # If we have direct results, return them
        if self.last_sparql_results is not None:
            return self.last_sparql_results

        # If we have a cache reference, load from Redis
        if self.results_ref and self._redis_client:
            try:
                cached_data = await self._redis_client.get(self.results_ref.cache_key)
                if cached_data:
                    return json.loads(cached_data)
                else:
                    logger.warning(f"Cached results not found for key: {self.results_ref.cache_key}")
                    return None
            except Exception as e:
                logger.error(f"Error loading cached results: {e}")
                return None

        # Fallback: try latest from history
        if self.results_history:
            latest = self.results_history[-1]
            return await self.get_full_results_by_id(latest.entry_id)

        return None

    def get_results_for_llm(self, entry_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get results in a format suitable for LLM context.
        If entry_id is provided, get specific results from history.
        Returns sample + metadata for cached/large results, or full results if small.
        """
        # If specific entry requested, get from history
        if entry_id:
            entry = self.get_result_by_id(entry_id)
            if entry:
                return {
                    "type": "history",
                    "entry_id": entry.entry_id,
                    "description": entry.description,
                    "total_count": entry.total_count,
                    "variables": entry.variables,
                    "sample": entry.sample,
                    "data_sources": entry.data_sources,
                    "note": f"Showing {len(entry.sample)} of {entry.total_count} results."
                }
            return {"type": "none", "results": None, "error": f"Entry {entry_id} not found"}

        # Default: current/latest results
        if self.last_sparql_results is not None:
            return {
                "type": "direct",
                "total_count": len(self.last_sparql_results),
                "results": self.last_sparql_results
            }

        if self.results_ref:
            return {
                "type": "cached",
                "total_count": self.results_ref.total_count,
                "variables": self.results_ref.variables,
                "sample": self.results_ref.sample,
                "note": f"Showing {len(self.results_ref.sample)} of {self.results_ref.total_count} results. The full data is available in the cache."
            }

        # Fallback: latest from history
        if self.results_history:
            latest = self.results_history[-1]
            return self.get_results_for_llm(latest.entry_id)

        return {"type": "none", "results": None}

    def has_results(self) -> bool:
        """Check if any results are available (direct, cached, or in history)"""
        return (
            self.last_sparql_results is not None
            or self.results_ref is not None
            or len(self.results_history) > 0
        )


# Intent Classification Prompt
INTENT_CLASSIFICATION_PROMPT = """You classify user intents for an ESG data extraction system.

CONTEXT:
- Workspace: {workspace_id}
- Active session: {has_session}
- Most recent data sources: {last_data_sources}
- SPARQL results on hand: {has_results}

CONVERSATION SO FAR:
{conversation_history}

CATEGORIES:

1. DATA_EXTRACTION - pull new data out of the files
   Signals: "extract", "show me", "what is", "list", "find", "which", "give me"
   Examples: "Extract the CO2 values", "Show me all materials", "What is the water consumption?"

2. FOLLOW_UP_QUERY - a follow-up about data that has already been extracted
   Requires: results already exist AND the request refers to them
   Signals: "sort", "filter", "average", "of those", "these", "only", "more than"
   Examples: "Sort by weight", "Only values above 100", "What is the average of those?"

3. CORPUS_INFO - a question about which files are available (NO extraction)
   Signals: "which files", "what is there", "available", "overview", "what can I ask"
   Examples: "What data do I have?", "What models are there?", "What is in the corpus?"

4. DATA_VISUALIZATION - chart or plot the data
   Requires: results already exist
   Signals: "diagram", "plot", "visualise", "graphic", "chart", "bars", "curve"
   Examples: "Create a bar chart", "Plot the CO2 values", "Visualise that"

5. DATA_CALCULATION - calculations, aggregations or unit conversions on extracted data
   Requires: results already exist
   Signals: "calculate", "sum", "average", "mean", "aggregate", "total up",
            "carbon footprint", "score", "convert", "unit", "per",
            "ESG score", "energy efficiency", "material efficiency", "total value"
   Examples: "Calculate the total emissions", "What is the carbon footprint per product?",
             "Calculate the average", "Sum by category", "Calculate the ESG score"

6. NEW_QUERY - the user wants DIFFERENT data from DIFFERENT files (a context switch)
   Signals: "now to", "instead", "different data", "switch to", "now the"
   IMPORTANT: only when other data sources are explicitly asked for
   Examples: "Now to the transport data", "Show material instead", "Now the EoL data"

HOW TO DECIDE:
- No session or results yet -> DATA_EXTRACTION or CORPUS_INFO
- Results exist and the question is about them -> FOLLOW_UP_QUERY
- Results exist and a chart is wanted -> DATA_VISUALIZATION
- Results exist and a calculation or aggregation is wanted -> DATA_CALCULATION
- Results exist but completely different data is wanted -> NEW_QUERY

USER REQUEST: {user_query}

Reply with the intent name ONLY (e.g. "DATA_EXTRACTION"):"""


# Plan Generation Prompt
PLAN_GENERATION_PROMPT = """You are the planning agent for an ESG data extraction system. Draw up a structured execution plan.

CONTEXT:
- Workspace: {workspace_id}
- Active session: {has_session}
- Results on hand: {has_results}
- Most recent data sources: {last_data_sources}

CONVERSATION SO FAR:
{conversation_history}

RESULTS HISTORY (data already extracted in this session):
{results_history}

AVAILABLE STEP TYPES:
1. DATA_EXTRACTION - pull new data out of the files via SPARQL
   Examples: "Show all materials", "Extract the CO2 values"

2. FOLLOW_UP_QUERY - a follow-up on data already extracted (filter, sort, aggregate)
   Requires: results must already exist!
   Examples: "Sort by weight", "Only values above 100"
   IMPORTANT: to reach back to EARLIER results, set "uses_result"!

3. CORPUS_INFO - information about the files available in the workspace
   Examples: "What data is available?", "What files are there?"
   CAREFUL: use this ONLY when the user EXPLICITLY asks about the data corpus!

4. DATA_VISUALIZATION - build a chart from the data
   Requires: results must already exist!
   Examples: "Create a bar chart", "Plot the values"
   IMPORTANT: to chart a particular result set, set "uses_result"!

5. DATA_CALCULATION - calculations, aggregations or unit conversions on extracted data
   Requires: results must already exist!
   Examples: "Calculate the carbon footprint", "Sum by category", "Calculate the ESG score",
             "What is the average?", "Convert to tonnes"
   IMPORTANT: this chains nicely into DATA_VISUALIZATION (compute first, then chart)
   IMPORTANT: to compute over a particular result set, set "uses_result"!

6. NEW_QUERY - reset the context and query entirely new data
   Examples: "Now to the transport data", "Show material instead"

CONDITIONAL EXECUTION (condition):
- "always": always run (the default)
- "previous_success": only if the previous step succeeded
- "previous_failed": only if the previous step failed
- "has_results": only if results are available
- "no_results": only if NO results are available

REFERENCING RESULTS (uses_result):
- When a step needs SPECIFIC earlier results, name the ID
- "latest" = the most recent results (assumed when nothing is given)
- "result_1", "result_2", etc. = a specific earlier result set from the history
- USE THIS whenever the user points back at earlier data (e.g. "the materials from before")

RULES:
- DATA_VISUALIZATION ALWAYS needs a prior DATA_EXTRACTION or existing results
- DATA_CALCULATION ALWAYS needs a prior DATA_EXTRACTION or existing results
- FOLLOW_UP_QUERY needs a prior DATA_EXTRACTION or existing results
- DATA_VISUALIZATION may follow DATA_CALCULATION (charting the computed values)
- Simple requests get exactly ONE step
- NO NEW EXTRACTION when the user is referring to data that already exists - use uses_result!

CRITICAL - SUB_QUERY RULES:
- For DATA_EXTRACTION the sub_query MUST be the user's EXACT original wording. No rephrasing, no interpretation, no simplification!
- WRONG: user asks "Compare the number of charging stations in Wuppertal and Rostock" -> sub_query: "Extract all charging stations..." (WRONG!)
- RIGHT: user asks "Compare the number of charging stations in Wuppertal and Rostock" -> sub_query: "Compare the number of charging stations in Wuppertal and Rostock" (RIGHT!)
- The SPARQL generator needs the user's full intent (words like "compare", "number of", "count") to build the right query!
- Only for follow-ups (FOLLOW_UP, VISUALIZATION, CALCULATION) may the sub_query describe the action instead

USER REQUEST: {user_query}

Reply with a JSON object ONLY, no commentary:
{{
  "steps": [
    {{"step_number": 1, "intent": "DATA_EXTRACTION", "sub_query": "Show all materials with their quantities", "depends_on": null, "condition": "always", "uses_result": null}},
    {{"step_number": 2, "intent": "DATA_VISUALIZATION", "sub_query": "Create a bar chart of the material quantities", "depends_on": 1, "condition": "has_results", "uses_result": "latest"}}
  ]
}}

An example that references earlier results:
{{
  "steps": [
    {{"step_number": 1, "intent": "DATA_VISUALIZATION", "sub_query": "Create a chart of the material data", "depends_on": null, "condition": "always", "uses_result": "result_1"}}
  ]
}}

An example that computes first and charts afterwards:
{{
  "steps": [
    {{"step_number": 1, "intent": "DATA_CALCULATION", "sub_query": "Calculate the carbon footprint per product", "depends_on": null, "condition": "has_results", "uses_result": "latest"}},
    {{"step_number": 2, "intent": "DATA_VISUALIZATION", "sub_query": "Create a bar chart of the calculated CO2 values", "depends_on": 1, "condition": "previous_success", "uses_result": null}}
  ]
}}"""


# Intermediate Message Generation Prompt
INTERMEDIATE_MESSAGE_PROMPT = """You are DINa, a friendly assistant for questions about a data space.
Write a short progress note about what you are doing right now.

STEP: {step_number} of {total_steps}
ACTION: {intent_description}
SUB-QUERY: {sub_query}
PREVIOUS CONTEXT: {previous_context}

Write one or two sentences. Examples of the tone to aim for:
- "Let me look for the relevant data sources..."
- "Found the data. Now putting the chart together..."
- "Checking which datasets fit your question..."

IMPORTANT: Reply in {language}. Answer with the message itself, no quotation marks:"""


# Summary Generation Prompt
SUMMARY_GENERATION_PROMPT = """You are DINa, a friendly assistant for questions about a data space.
Summarise what was done.

ORIGINAL QUESTION: {original_query}

STEPS TAKEN:
{executed_steps}

RESULTS:
{results_summary}

Write two to four sentences that confirm what happened, highlight the key
findings, and mention any chart that was produced.

IMPORTANT: Reply in {language}. Answer with the summary itself, no preamble:"""


# Error Analysis Prompt
ERROR_ANALYSIS_PROMPT = """You analyse failures and propose ways forward.

THE STEP THAT FAILED:
- Action: {intent}
- Request: {sub_query}
- Error: {error_message}

CONTEXT:
- Data sources available: {data_sources}
- Earlier results: {has_previous_results}

LIKELY CAUSES:
1. The search terms or spelling were off
2. The data simply is not present in the sources
3. Something broke technically during processing

Work out what went wrong and reply with a JSON object:
{{
  "can_retry": true/false,
  "alternative_query": "a different phrasing, where one makes sense",
  "user_message": "a friendly explanation for the user",
  "needs_user_input": true/false
}}"""


# Visualization Code Generation Prompt
# Note: Use {{ and }} to escape curly braces in the example code
# DINa Color Palette for consistent branding
DINA_COLORS = {
    'primary': '#164475',       # Dark blue
    'accent': '#C6712F',        # Orange
    'primary_light': '#5a87be', # Lighter blue
    'accent_light': '#d4894f',  # Lighter orange
    'primary_dark': '#0f3159',  # Very dark blue
    'accent_dark': '#a85d26',   # Dark orange
}

VISUALIZATION_GENERATION_PROMPT = """You are an expert at plotting data in Python. Write the matplotlib code for a chart.

AVAILABLE DATA (from a SPARQL query):
Variables: {variables}
Sample rows (first 5):
{sample_data}

USER REQUEST: {user_query}

REQUIREMENTS:
1. Use matplotlib ONLY (import matplotlib.pyplot as plt)
2. The data arrives as a list of dictionaries in the variable 'data'
3. Pick a chart type that actually suits the request
4. Label both axes and give the chart a title
5. Finish with plt.tight_layout()
6. NO print statements, NO plt.show()
7. IMPORTANT: unless the user asks for specific colours, ALWAYS use the DINa palette:
   - Primary (blue): '#164475'
   - Accent (orange): '#C6712F'
   - Further colours if needed: '#5a87be' (light blue), '#d4894f' (light orange), '#0f3159' (dark blue), '#a85d26' (dark orange)
   - Bar charts: blue ('#164475') as the default
   - Pie charts: alternate between the blues and the oranges
   - Line charts: first line blue, second orange, and so on

EXAMPLE SHAPE:
```python
import matplotlib.pyplot as plt

# DINa colour palette
DINA_BLUE = '#164475'
DINA_ORANGE = '#C6712F'
DINA_COLORS = ['#164475', '#C6712F', '#5a87be', '#d4894f', '#0f3159', '#a85d26']

# Pull out the data
labels = [d.get('variable1', {{}}).get('value', '') for d in data]
values = [float(d.get('variable2', {{}}).get('value', 0)) for d in data]

# Draw the chart in the DINa colours
fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(labels, values, color=DINA_BLUE, edgecolor='white')
ax.set_xlabel('X axis', fontsize=12, color='#333333')
ax.set_ylabel('Y axis', fontsize=12, color='#333333')
ax.set_title('Title', fontsize=14, fontweight='bold', color=DINA_BLUE)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
```

Write the Python code:
```python"""


# Calculation Code Generation Prompt
# Note: Use {{ and }} to escape curly braces in the example code
CALCULATION_GENERATION_PROMPT = """You are an expert at ESG data analysis in Python.
Write Python code that computes and aggregates over extracted data.

AVAILABLE DATA (from a SPARQL query):
Variables: {variables}
Sample rows (first 5):
{sample_data}

USER REQUEST: {user_query}

CONTEXT WORTH KNOWING:
{context_info}

REQUIREMENTS:
1. The data arrives as a list of dictionaries in the variable 'data'
2. Every value has the shape: {{"value": "...", "type": "literal/uri"}}
3. Build a dictionary named 'calculation_result' with EXACTLY this structure:
   - 'summary': dict of headline figures (e.g. {{"Total CO2": 1234.5, "Average": 123.4}})
   - 'table': list of dicts for tabular output (e.g. [{{"Product": "A", "CO2": 100}}, ...])
   - 'metadata': dict of units and descriptions (e.g. {{"unit": "kg CO2", "description": "..."}})
4. Guard every calculation with try/except
5. NO print statements, NO imports (math and statistics are already available)

TYPICAL ESG CALCULATIONS:
- Carbon footprint: the sum of all emission values, weighted where appropriate
- ESG score: a weighted average (E: 40%, S: 30%, G: 30%)
- Energy efficiency: energy per unit (kWh per item)
- Material efficiency: the output-to-input ratio
- Average / median: the usual aggregations
- Unit conversion: kg to tonnes, kWh to MWh, and so on

EXAMPLE SHAPE:
```python
# Pull out the data and coerce it
values = []
for d in data:
    try:
        val = float(d.get('co2_value', {{}}).get('value', 0))
        name = d.get('product_name', {{}}).get('value', 'Unknown')
        values.append({{"name": name, "value": val}})
    except (ValueError, TypeError):
        continue

# Do the maths
total = sum(v['value'] for v in values)
average = total / len(values) if values else 0

# Shape the result
calculation_result = {{
    'summary': {{
        'Total CO2': round(total, 2),
        'Average': round(average, 2),
        'Row count': len(values)
    }},
    'table': [
        {{'Product': v['name'], 'CO2 (kg)': round(v['value'], 2)}}
        for v in sorted(values, key=lambda x: x['value'], reverse=True)
    ],
    'metadata': {{
        'unit': 'kg CO2',
        'calculation_type': 'Aggregation',
        'description': 'CO2 emissions per product'
    }}
}}
```

Write the Python code:
```python"""


# =============================================================================
# GENERATED CODE EXECUTION
#
# Charts and derived figures are produced by running Python that the language
# model wrote. The globals handed to exec() are restricted, but a restricted
# globals mapping is not a security boundary in CPython: given enough effort,
# generated code can still reach the interpreter. Treat this as a convenience
# for trusted, authenticated users - not as a sandbox.
#
# The screen below rejects the constructs most often used to break out, so an
# obviously unsafe snippet fails before it runs. Deployments that expose this
# service beyond a trusted group should run the backend in an isolated
# container with no network access and no credentials worth stealing.
# =============================================================================
_FORBIDDEN_CODE_PATTERNS = (
    "__import__", "__builtins__", "__subclasses__", "__globals__", "__class__",
    "__bases__", "__mro__", "__code__", "importlib", "subprocess", "socket",
    "eval(", "exec(", "compile(", "open(", "os.", "sys.", "shutil", "pathlib",
)


def screen_generated_code(code: str) -> Optional[str]:
    """Return the first forbidden construct found, or None if the code passes."""
    for pattern in _FORBIDDEN_CODE_PATTERNS:
        if pattern in code:
            return pattern
    return None


def describe_reply_language(user_query: str) -> str:
    """Describe, for the prompt, which language the answer should be written in.

    The user's own wording is the most reliable signal available here: the chat
    stream carries no locale, and asking the model to mirror the question keeps
    the answer in the language the person actually used.
    """
    return (
        "the same language as this question, matching it exactly: "
        f"\"{user_query.strip()[:200]}\""
        if user_query and user_query.strip()
        else "English"
    )


class OrchestratingAgent:
    """
    Orchestrating Agent that classifies user intents and routes requests
    to appropriate handlers.
    """

    def __init__(
        self,
        llm: Union[OllamaLLM, DeepSeekLLM, OpenAILLM],
        workspace_id: str,
        context: Optional[AgentContext] = None,
        llm_profile: str = "deepseek_chat"
    ):
        self.llm = llm
        self.workspace_id = workspace_id
        self.context = context or AgentContext(workspace_id=workspace_id)
        self.llm_profile = llm_profile
        self.request_ts = datetime.now(timezone.utc).isoformat()
        self._redis_client = None  # Set via route_and_execute

    async def store_results_to_cache(
        self,
        results: List[Dict],
        redis_client,
        variables: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Store SPARQL results either directly in context (small sets) or in Redis cache (large sets).

        - Results with <= MAX_SPARQL_RESULTS_IN_CONTEXT rows are stored directly
        - Larger results are stored in Redis with a ResultsReference in context

        Args:
            results: The SPARQL query results
            redis_client: Redis client for caching
            variables: Optional list of variable names from the query

        Returns:
            The cache key if results were cached in Redis, None otherwise
        """
        if not results:
            self.context.last_sparql_results = None
            self.context.results_ref = None
            return None

        # Determine variables if not provided
        if variables is None and results:
            variables = list(results[0].keys())

        # Small result sets: store directly in context
        if len(results) <= MAX_SPARQL_RESULTS_IN_CONTEXT:
            self.context.last_sparql_results = results
            self.context.last_sparql_variables = variables
            self.context.results_ref = None
            logger.info(f"[Agent] Stored {len(results)} results directly in context")
            return None

        # Large result sets: cache in Redis and store reference
        cache_key = f"sparql_results:{self.context.session_id}:{uuid.uuid4().hex[:8]}"

        try:
            # Store full results in Redis
            await redis_client.set(
                cache_key,
                json.dumps(results),
                ex=RESULTS_CACHE_TTL
            )

            # Create reference with sample
            sample_size = min(5, len(results))
            self.context.results_ref = ResultsReference(
                cache_key=cache_key,
                total_count=len(results),
                variables=variables,
                sample=results[:sample_size]
            )

            # Clear direct results since we're using cache
            self.context.last_sparql_results = None
            self.context.last_sparql_variables = variables

            # Set Redis client for lazy loading
            self.context.set_redis_client(redis_client)

            logger.info(
                f"[Agent] Cached {len(results)} results in Redis (key: {cache_key}), "
                f"keeping {sample_size} sample rows in context"
            )
            return cache_key

        except Exception as e:
            logger.error(f"[Agent] Failed to cache results in Redis: {e}")
            # Fallback: store directly (may cause issues with very large sets)
            self.context.last_sparql_results = results
            self.context.last_sparql_variables = variables
            self.context.results_ref = None
            return None

    def trim_conversation_history(self) -> None:
        """
        Apply sliding window to conversation history to prevent context overflow.
        Keeps only the last MAX_CONVERSATION_HISTORY messages.
        """
        if len(self.context.conversation_history) > MAX_CONVERSATION_HISTORY:
            # Keep the most recent messages
            trimmed_count = len(self.context.conversation_history) - MAX_CONVERSATION_HISTORY
            self.context.conversation_history = self.context.conversation_history[-MAX_CONVERSATION_HISTORY:]
            logger.info(f"[Agent] Trimmed conversation history, removed {trimmed_count} old messages")


    # =========================================================================
    # Solid/Comunica Integration Methods
    # =========================================================================

    async def continue_plan_execution(
        self,
        db_session,
        settings,
        agentic_reasoning_enabled: bool = False,
        internal_reasoning_enabled: bool = False,
        few_shot_prompting_enabled: bool = False,
        interactive_mode: bool = False,
        redis_client=None
    ) -> AsyncGenerator[str, None]:
        """
        Continue executing a plan after Comunica results have been received.
        This is called from the /continue-plan endpoint.
        """
        if not self.context.current_plan:
            logger.warning("[Agent] No current plan to continue")
            yield await format_sse_event({
                "message": "There is no active plan to continue",
                "step_id": "no_plan"
            }, "pipeline_update")
            return

        plan = self.context.current_plan
        logger.info(f"[Agent] Continuing plan execution from step {plan.current_step}")

        # Set redis client if provided
        if redis_client:
            self._redis_client = redis_client

        # Execute remaining pending steps using the same logic as execute_plan
        from .utils import stream_message_fake

        previous_context = ""

        for step in plan.steps:
            if step.status != "pending":
                continue

            plan.current_step = step.step_number

            # Check condition
            if not self.check_step_condition(step, plan):
                step.status = "skipped"
                logger.info(f"[Agent] Skipping step {step.step_number} - condition not met")
                yield await format_sse_event({
                    "message": f"Step {step.step_number} skipped (its condition was not met)",
                    "step_id": f"plan_step_{step.step_number}_skipped",
                    "step_number": step.step_number,
                    "total_steps": len(plan.steps),
                    "request_timestamp": self.request_ts
                }, "pipeline_update")
                continue

            step.status = "running"
            logger.info(f"[Agent] Executing pending step {step.step_number}: {step.intent.value}")

            # Get handler for this intent
            handler = self._get_handler(step.intent)

            # Execute handler
            try:
                async for event in handler(
                    user_query=step.sub_query,
                    db_session=db_session,
                    settings=settings,
                    agentic_reasoning_enabled=agentic_reasoning_enabled,
                    internal_reasoning_enabled=internal_reasoning_enabled,
                    few_shot_prompting_enabled=few_shot_prompting_enabled,
                    interactive_mode=interactive_mode,
                    current_step=step,
                    current_plan=plan
                ):
                    yield event

                # Mark as completed if not already set differently
                if step.status == "running":
                    step.status = "completed"

            except Exception as e:
                logger.error(f"[Agent] Step {step.step_number} failed: {e}", exc_info=True)
                step.status = "failed"
                step.error_message = str(e)
                yield await format_sse_event({
                    "message": f"Step {step.step_number} failed: {str(e)}",
                    "step_id": f"plan_step_{step.step_number}_error",
                    "is_error": True
                }, "pipeline_error")

        # Generate summary if needed
        if plan.summary_required:
            completed_steps = sum(1 for s in plan.steps if s.status == "completed")
            yield await format_sse_event({
                "message": f"Plan finished ({completed_steps}/{len(plan.steps)} steps)",
                "step_id": "plan_completed",
                "total_steps": len(plan.steps),
                "completed_steps": completed_steps
            }, "plan_summary")

    def _generate_result_description(
        self,
        user_query: str,
        variables: List[str],
        result_count: int
    ) -> str:
        """
        Generate a short description for a result set based on the query and variables.
        Used for results history entries.
        """
        # Truncate long queries
        query_short = user_query[:50] + "..." if len(user_query) > 50 else user_query

        # Create description based on variables
        if variables:
            main_vars = ", ".join(variables[:3])
            if len(variables) > 3:
                main_vars += f" (+{len(variables) - 3} more)"
            return f"{query_short} - {result_count} results ({main_vars})"
        else:
            return f"{query_short} - {result_count} results"

    def _format_conversation_history(self, max_messages: int = 10) -> str:
        """Format conversation history for inclusion in prompts."""
        if not self.context.conversation_history:
            return "(no earlier messages)"

        # Take the last N messages
        recent = self.context.conversation_history[-max_messages:]
        formatted = []
        for msg in recent:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            # Truncate very long messages
            if len(content) > 300:
                content = content[:300] + "..."
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted) if formatted else "(no earlier messages)"

    async def classify_intent(self, user_query: str) -> AgentIntent:
        """
        Classify user intent using LLM with context awareness.
        """
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            workspace_id=self.workspace_id,
            has_session="yes" if self.context.session_id else "no",
            last_data_sources=", ".join(self.context.last_data_sources) if self.context.last_data_sources else "none",
            has_results="yes" if self.context.last_sparql_results else "no",
            conversation_history=self._format_conversation_history(),
            user_query=user_query
        )

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            response_clean = response.strip().upper()

            # Map response to intent
            intent_mapping = {
                "DATA_EXTRACTION": AgentIntent.DATA_EXTRACTION,
                "FOLLOW_UP_QUERY": AgentIntent.FOLLOW_UP_QUERY,
                "CORPUS_INFO": AgentIntent.CORPUS_INFO,
                "DATA_VISUALIZATION": AgentIntent.DATA_VISUALIZATION,
                "DATA_CALCULATION": AgentIntent.DATA_CALCULATION,
                "NEW_QUERY": AgentIntent.NEW_QUERY,
            }

            for key, intent in intent_mapping.items():
                if key in response_clean:
                    logger.info(f"[Agent] Classified intent: {intent.value} for query: '{user_query[:50]}...'")
                    return intent

            # Default to data extraction if unclear
            logger.warning(f"[Agent] Could not classify intent from response: {response_clean}, defaulting to DATA_EXTRACTION")
            return AgentIntent.DATA_EXTRACTION

        except Exception as e:
            logger.error(f"[Agent] Error classifying intent: {e}", exc_info=True)
            return AgentIntent.DATA_EXTRACTION

    async def _is_different_data_source(self, user_query: str) -> bool:
        """
        Check if the user query refers to different data sources than the current session.
        Returns True if a new session should be started.
        """
        if not self.context.last_data_sources:
            return False

        # Use LLM to check if query refers to different data
        check_prompt = f"""Decide whether this request concerns the same data as before, or different data.

Data sources currently in the session: {', '.join(self.context.last_data_sources)}
Previous request: {self.context.last_user_query or 'none'}

New request: {user_query}

Does the new request concern:
- GLEICHE_DATEN: the same data sources and topics as before
- ANDERE_DATEN: entirely different data sources or topics

Reply with GLEICHE_DATEN or ANDERE_DATEN and nothing else:"""

        try:
            response = await asyncio.to_thread(self.llm.invoke, check_prompt)
            return "ANDERE_DATEN" in response.upper()
        except Exception as e:
            logger.error(f"[Agent] Error checking data source: {e}")
            return False

    # ==================== NEW PLAN-BASED METHODS ====================

    async def generate_execution_plan(self, user_query: str) -> ExecutionPlan:
        """
        Generate an execution plan for the user query.
        Always returns a plan, even for simple single-step queries.
        Includes results history for agent to reference previous extractions.
        """
        import re

        # Get results history summary for the prompt
        results_history = self.context.get_results_history_summary()

        prompt = PLAN_GENERATION_PROMPT.format(
            workspace_id=self.workspace_id,
            has_session="yes" if self.context.session_id else "no",
            has_results="yes" if self.context.has_results() else "no",
            last_data_sources=", ".join(self.context.last_data_sources) if self.context.last_data_sources else "none",
            conversation_history=self._format_conversation_history(),
            results_history=results_history,
            user_query=user_query
        )

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                plan_data = json.loads(json_match.group())

                steps = []
                for step_data in plan_data.get("steps", []):
                    # Parse intent
                    intent_str = step_data.get("intent", "DATA_EXTRACTION").upper()
                    intent = AgentIntent[intent_str] if intent_str in AgentIntent.__members__ else AgentIntent.DATA_EXTRACTION

                    # Parse condition
                    condition_str = step_data.get("condition", "always").lower()
                    condition = None
                    if condition_str in [c.value for c in StepCondition]:
                        condition = StepCondition(condition_str)

                    # Parse uses_result reference
                    uses_result = step_data.get("uses_result")
                    if uses_result and uses_result.lower() == "null":
                        uses_result = None

                    step = ExecutionStep(
                        step_number=step_data.get("step_number", len(steps) + 1),
                        intent=intent,
                        sub_query=step_data.get("sub_query", user_query),
                        depends_on=step_data.get("depends_on"),
                        condition=condition,
                        uses_result=uses_result
                    )
                    steps.append(step)

                if steps:
                    # Log which steps use result references
                    for step in steps:
                        if step.uses_result:
                            logger.info(f"[Agent] Step {step.step_number} uses result reference: {step.uses_result}")
                    logger.info(f"[Agent] Generated plan with {len(steps)} steps")
                    return ExecutionPlan(
                        original_query=user_query,
                        steps=steps,
                        plan_id=str(uuid.uuid4())
                    )

        except json.JSONDecodeError as e:
            logger.error(f"[Agent] JSON parsing error in plan generation: {e}")
        except KeyError as e:
            logger.error(f"[Agent] Invalid intent in plan: {e}")
        except Exception as e:
            logger.error(f"[Agent] Error generating plan: {e}", exc_info=True)

        # Fallback: Use classify_intent for single-step plan
        logger.warning("[Agent] Falling back to single-step plan via classify_intent")
        intent = await self.classify_intent(user_query)
        return ExecutionPlan(
            original_query=user_query,
            steps=[ExecutionStep(
                step_number=1,
                intent=intent,
                sub_query=user_query,
                condition=StepCondition.ALWAYS
            )],
            plan_id=str(uuid.uuid4())
        )

    def check_step_condition(self, step: ExecutionStep, plan: ExecutionPlan) -> bool:
        """
        Check if a step's condition is satisfied.
        Returns True if the step should be executed.
        """
        if step.condition is None or step.condition == StepCondition.ALWAYS:
            return True

        # Get previous step if exists
        prev_step = None
        if step.depends_on:
            for s in plan.steps:
                if s.step_number == step.depends_on:
                    prev_step = s
                    break
        elif step.step_number > 1:
            prev_step = plan.steps[step.step_number - 2]

        if step.condition == StepCondition.PREVIOUS_SUCCESS:
            return prev_step is not None and prev_step.status == "completed"

        elif step.condition == StepCondition.PREVIOUS_FAILED:
            return prev_step is not None and prev_step.status == "failed"

        elif step.condition == StepCondition.HAS_RESULTS:
            # Check if step references specific results or uses general check
            if step.uses_result:
                entry = self.context.get_result_by_id(step.uses_result)
                return entry is not None
            return self.context.has_results()

        elif step.condition == StepCondition.NO_RESULTS:
            return not self.context.has_results()

        return True

    async def generate_intermediate_message(
        self,
        step: ExecutionStep,
        plan: ExecutionPlan,
        previous_context: str = ""
    ) -> str:
        """
        Generate a natural intermediate message for the current step.
        """
        prompt = INTERMEDIATE_MESSAGE_PROMPT.format(
            step_number=step.step_number,
            total_steps=len(plan.steps),
            intent_description=self._get_intent_description(step.intent),
            sub_query=step.sub_query,
            previous_context=previous_context or "no previous results",
            language=describe_reply_language(plan.original_query),
        )

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"[Agent] Error generating intermediate message: {e}")
            # Fallback messages
            fallback_messages = {
                AgentIntent.DATA_EXTRACTION: "Looking for the data you asked about...",
                AgentIntent.FOLLOW_UP_QUERY: "Working on your follow-up...",
                AgentIntent.CORPUS_INFO: "Checking which files are available...",
                AgentIntent.DATA_VISUALIZATION: "Putting the chart together...",
                AgentIntent.NEW_QUERY: "Starting a fresh data query...",
            }
            return fallback_messages.get(step.intent, "Working on it...")

    async def generate_summary(self, plan: ExecutionPlan) -> str:
        """
        Generate a natural summary of the executed plan.
        """
        # Build executed steps description
        executed_steps = []
        for step in plan.steps:
            status_text = {
                "completed": "succeeded",
                "failed": "failed",
                "skipped": "skipped"
            }.get(step.status, step.status)
            executed_steps.append(
                f"Step {step.step_number}: {self._get_intent_description(step.intent)} - \"{step.sub_query}\" [{status_text}]"
            )

        # Build results summary
        results_summary = []
        for step in plan.steps:
            if step.status == "completed":
                if step.intent == AgentIntent.DATA_EXTRACTION:
                    count = len(self.context.last_sparql_results or [])
                    results_summary.append(f"Data extraction: {count} rows found")
                elif step.intent == AgentIntent.DATA_VISUALIZATION:
                    results_summary.append("Visualisation: a chart was created")
                elif step.intent == AgentIntent.CORPUS_INFO:
                    results_summary.append("Corpus info: the files were listed")
                elif step.intent == AgentIntent.FOLLOW_UP_QUERY:
                    count = len(self.context.last_sparql_results or [])
                    results_summary.append(f"Follow-up: {count} rows")

        prompt = SUMMARY_GENERATION_PROMPT.format(
            original_query=plan.original_query,
            executed_steps="\n".join(executed_steps),
            results_summary="\n".join(results_summary) if results_summary else "nothing noteworthy",
            language=describe_reply_language(plan.original_query),
        )

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"[Agent] Error generating summary: {e}")
            completed = sum(1 for s in plan.steps if s.status == "completed")
            return f"I completed {completed} of {len(plan.steps)} steps successfully."

    async def handle_step_error(
        self,
        step: ExecutionStep,
        error: Exception,
        plan: ExecutionPlan
    ) -> Dict[str, Any]:
        """
        Analyze a step error and decide on recovery strategy.
        Returns dict with: can_retry, alternative_query, user_message, needs_user_input
        """
        prompt = ERROR_ANALYSIS_PROMPT.format(
            intent=step.intent.value,
            sub_query=step.sub_query,
            error_message=str(error),
            data_sources=", ".join(self.context.last_data_sources) if self.context.last_data_sources else "none known",
            has_previous_results="yes" if self.context.last_sparql_results else "no"
        )

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)

            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"[Agent] Error analyzing step error: {e}")

        # Default response
        return {
            "can_retry": False,
            "alternative_query": None,
            "user_message": f"Something went wrong while processing this: {str(error)}",
            "needs_user_input": True
        }

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        db_session,
        settings,
        agentic_reasoning_enabled: bool = False,
        internal_reasoning_enabled: bool = False,
        few_shot_prompting_enabled: bool = False,
        interactive_mode: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Execute an execution plan step by step.
        Yields SSE events for each step and generates natural messages.
        """
        from .utils import stream_message_fake

        logger.info(f"[Agent] Executing plan with {len(plan.steps)} steps")

        previous_context = ""

        for step in plan.steps:
            plan.current_step = step.step_number

            # Check condition
            if not self.check_step_condition(step, plan):
                step.status = "skipped"
                logger.info(f"[Agent] Skipping step {step.step_number} - condition not met")
                yield await format_sse_event({
                    "message": f"Step {step.step_number} skipped (its condition was not met)",
                    "step_id": f"plan_step_{step.step_number}_skipped",
                    "step_number": step.step_number,
                    "total_steps": len(plan.steps),
                    "request_timestamp": self.request_ts
                }, "pipeline_update")
                continue

            step.status = "running"

            # Generate and stream intermediate message
            intermediate_msg = await self.generate_intermediate_message(step, plan, previous_context)
            async for event in stream_message_fake(
                message=intermediate_msg,
                sender="dina",
                step_id=f"intermediate_message_{step.step_number}",
                request_timestamp=self.request_ts,
                delay_between_chars=0.008,
                delay_between_words=0.03
            ):
                yield event

            # Emit step start event
            yield await format_sse_event({
                "message": f"Step {step.step_number}/{len(plan.steps)}: {self._get_intent_description(step.intent)}",
                "step_id": f"plan_step_{step.step_number}_start",
                "intent": step.intent.value,
                "sub_query": step.sub_query,
                "step_number": step.step_number,
                "total_steps": len(plan.steps),
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            try:
                # Execute the handler for this step
                handler = self._get_handler(step.intent)

                # For extraction and follow-up handlers, pass the step and plan so they can set awaiting_comunica
                if step.intent in (AgentIntent.DATA_EXTRACTION, AgentIntent.FOLLOW_UP_QUERY):
                    async for event in handler(
                        user_query=step.sub_query,
                        db_session=db_session,
                        settings=settings,
                        agentic_reasoning_enabled=agentic_reasoning_enabled,
                        internal_reasoning_enabled=internal_reasoning_enabled,
                        few_shot_prompting_enabled=few_shot_prompting_enabled,
                        interactive_mode=interactive_mode,
                        current_step=step,
                        current_plan=plan
                    ):
                        yield event
                else:
                    async for event in handler(
                        user_query=step.sub_query,
                        db_session=db_session,
                        settings=settings,
                        agentic_reasoning_enabled=agentic_reasoning_enabled,
                        internal_reasoning_enabled=internal_reasoning_enabled,
                        few_shot_prompting_enabled=few_shot_prompting_enabled,
                        interactive_mode=interactive_mode
                    ):
                        yield event

                # Check if the step is now awaiting clarification (set by the handler)
                if step.status == "awaiting_clarification":
                    logger.info(f"[Agent] Step {step.step_number} is awaiting clarification - pausing plan execution")

                    # Store the plan for later resumption
                    self.context.current_plan = plan

                    # Emit a special event to signal the plan is paused (not failed!)
                    yield await format_sse_event({
                        "message": "Plan paused - waiting for the user's answer",
                        "step_id": "agent_plan_paused_for_clarification",
                        "plan_id": plan.plan_id,
                        "paused_step": step.step_number,
                        "clarification_data": step.clarification_data,
                        "request_timestamp": self.request_ts
                    }, "agent_clarification_required")

                    # Exit the plan execution loop - we'll resume later
                    return

                # Check if the step is awaiting Comunica execution (Solid mode)
                if step.status == "awaiting_comunica":
                    logger.info(f"[Agent] Step {step.step_number} is awaiting Comunica execution - pausing plan execution")

                    # Store the plan for later resumption
                    self.context.current_plan = plan

                    # Exit the plan execution loop - frontend will handle Comunica execution
                    # and call /continue-plan to resume
                    return

                step.status = "completed"

                # Update previous context for next step
                if self.context.last_sparql_results:
                    count = len(self.context.last_sparql_results)
                    previous_context = f"the previous step returned {count} results"

                # Emit step completed event
                yield await format_sse_event({
                    "message": f"Step {step.step_number} complete",
                    "step_id": f"plan_step_{step.step_number}_completed",
                    "step_number": step.step_number,
                    "total_steps": len(plan.steps),
                    "request_timestamp": self.request_ts
                }, "pipeline_update")

            except Exception as e:
                logger.error(f"[Agent] Step {step.step_number} failed: {e}", exc_info=True)
                step.status = "failed"
                step.error_message = str(e)

                # Try to handle the error
                error_analysis = await self.handle_step_error(step, e, plan)

                if error_analysis.get("can_retry") and error_analysis.get("alternative_query"):
                    # Retry with alternative query
                    retry_msg = "That first attempt did not work. Let me try a different angle..."
                    async for event in stream_message_fake(
                        message=retry_msg,
                        sender="dina",
                        step_id=f"step_{step.step_number}_retry",
                        request_timestamp=self.request_ts,
                        delay_between_chars=0.01,
                        delay_between_words=0.04
                    ):
                        yield event

                    # Retry with alternative query
                    step.sub_query = error_analysis["alternative_query"]
                    try:
                        handler = self._get_handler(step.intent)
                        # For extraction and follow-up handlers, pass the step and plan for awaiting_comunica handling
                        if step.intent in (AgentIntent.DATA_EXTRACTION, AgentIntent.FOLLOW_UP_QUERY):
                            async for event in handler(
                                user_query=step.sub_query,
                                db_session=db_session,
                                settings=settings,
                                agentic_reasoning_enabled=agentic_reasoning_enabled,
                                internal_reasoning_enabled=internal_reasoning_enabled,
                                few_shot_prompting_enabled=few_shot_prompting_enabled,
                                interactive_mode=interactive_mode,
                                current_step=step,
                                current_plan=plan
                            ):
                                yield event
                        else:
                            async for event in handler(
                                user_query=step.sub_query,
                                db_session=db_session,
                                settings=settings,
                                agentic_reasoning_enabled=agentic_reasoning_enabled,
                                internal_reasoning_enabled=internal_reasoning_enabled,
                                few_shot_prompting_enabled=few_shot_prompting_enabled,
                                interactive_mode=interactive_mode
                            ):
                                yield event

                        # Check if awaiting clarification after retry
                        if step.status == "awaiting_clarification":
                            self.context.current_plan = plan
                            yield await format_sse_event({
                                "message": "Plan paused - waiting for the user's answer",
                                "step_id": "agent_plan_paused_for_clarification",
                                "plan_id": plan.plan_id,
                                "paused_step": step.step_number,
                                "clarification_data": step.clarification_data,
                                "request_timestamp": self.request_ts
                            }, "agent_clarification_required")
                            return

                        # Check if awaiting Comunica execution after retry (Solid mode)
                        if step.status == "awaiting_comunica":
                            self.context.current_plan = plan
                            logger.info(f"[Agent] Step {step.step_number} awaiting Comunica after retry - pausing plan")
                            return

                        step.status = "completed"
                    except Exception as retry_error:
                        step.status = "failed"
                        step.error_message = str(retry_error)

                if step.status == "failed":
                    # Emit error message to user
                    user_message = error_analysis.get("user_message", f"Error: {str(e)}")
                    async for event in stream_message_fake(
                        message=user_message,
                        sender="dina",
                        step_id=f"step_{step.step_number}_error_message",
                        request_timestamp=self.request_ts,
                        delay_between_chars=0.01,
                        delay_between_words=0.04
                    ):
                        yield event

                    yield await format_sse_event({
                        "message": f"Step {step.step_number} failed",
                        "step_id": f"plan_step_{step.step_number}_failed",
                        "is_error": True,
                        "error_message": str(e),
                        "needs_user_input": error_analysis.get("needs_user_input", True),
                        "request_timestamp": self.request_ts
                    }, "pipeline_error")

                    # Continue with next steps if possible (don't break unless fatal)
                    if error_analysis.get("needs_user_input"):
                        yield await format_sse_event({
                            "message": "I need your help before I can carry on.",
                            "step_id": "user_input_required",
                            "failed_step": step.step_number,
                            "request_timestamp": self.request_ts
                        }, "user_input_required")

        # Generate and stream summary if there were completed steps
        completed_steps = [s for s in plan.steps if s.status == "completed"]
        if completed_steps and plan.summary_required:
            summary = await self.generate_summary(plan)
            async for event in stream_message_fake(
                message=summary,
                sender="dina",
                step_id="plan_summary",
                request_timestamp=self.request_ts,
                delay_between_chars=0.01,
                delay_between_words=0.04
            ):
                yield event


    # ==================== END NEW PLAN-BASED METHODS ====================

    async def route_and_execute(
        self,
        user_query: str,
        db_session,
        settings,
        agentic_reasoning_enabled: bool = False,
        internal_reasoning_enabled: bool = False,
        few_shot_prompting_enabled: bool = False,
        interactive_mode: bool = False,
        auto_execute_plans: bool = True,
        redis_client=None
    ) -> AsyncGenerator[str, None]:
        """
        Generate an execution plan and execute it.
        All queries go through the plan-based flow.
        Yields SSE events.

        Args:
            redis_client: Optional Redis client for caching large result sets
        """
        self.request_ts = datetime.now(timezone.utc).isoformat()

        # Set Redis client for context caching
        if redis_client:
            self.context.set_redis_client(redis_client)
        self._redis_client = redis_client

        # Announce plan generation
        yield await format_sse_event({
            "message": "Reading the request and drawing up an execution plan...",
            "step_id": "agent_plan_generating",
            "request_timestamp": self.request_ts
        }, "pipeline_update")

        # Generate execution plan
        plan = await self.generate_execution_plan(user_query)

        # Announce plan created
        yield await format_sse_event({
            "message": f"Plan ready: {len(plan.steps)} step(s)",
            "step_id": "agent_plan_created",
            "plan": plan.to_dict(),
            "step_count": len(plan.steps),
            "request_timestamp": self.request_ts
        }, "pipeline_update")

        # If auto_execute is disabled, wait for confirmation
        if not auto_execute_plans:
            plan.awaiting_confirmation = True
            yield await format_sse_event({
                "message": "The plan is waiting for confirmation",
                "step_id": "plan_confirmation_required",
                "plan": plan.to_dict(),
                "awaiting_confirmation": True,
                "request_timestamp": self.request_ts
            }, "plan_confirmation_required")
            # Store plan for later execution
            self.context.current_plan = plan
            return

        # Execute the plan
        async for event in self.execute_plan(
            plan=plan,
            db_session=db_session,
            settings=settings,
            agentic_reasoning_enabled=agentic_reasoning_enabled,
            internal_reasoning_enabled=internal_reasoning_enabled,
            few_shot_prompting_enabled=few_shot_prompting_enabled,
            interactive_mode=interactive_mode
        ):
            yield event

        # Update context
        self.context.last_user_query = user_query
        self.context.conversation_history.append({
            "role": "user",
            "content": user_query,
            "plan_id": plan.plan_id,
            "timestamp": self.request_ts
        })

    def _get_intent_description(self, intent: AgentIntent) -> str:
        """Get human-readable description of intent"""
        descriptions = {
            AgentIntent.DATA_EXTRACTION: "Data extraction",
            AgentIntent.FOLLOW_UP_QUERY: "Follow-up question",
            AgentIntent.CORPUS_INFO: "Corpus information",
            AgentIntent.DATA_VISUALIZATION: "Data visualisation",
            AgentIntent.DATA_CALCULATION: "Data calculation",
            AgentIntent.NEW_QUERY: "New request (different data)",
        }
        return descriptions.get(intent, "Unknown")

    def _get_handler(self, intent: AgentIntent):
        """Get the appropriate handler for the intent"""
        handlers = {
            AgentIntent.DATA_EXTRACTION: self._handle_extraction,
            AgentIntent.FOLLOW_UP_QUERY: self._handle_follow_up,
            AgentIntent.CORPUS_INFO: self._handle_corpus_info,
            AgentIntent.DATA_VISUALIZATION: self._handle_visualization,
            AgentIntent.DATA_CALCULATION: self._handle_calculation,
            AgentIntent.NEW_QUERY: self._handle_new_query,
        }
        return handlers[intent]

    # --- Handler Implementations ---

    async def _handle_extraction(
        self,
        user_query: str,
        db_session,
        settings,
        agentic_reasoning_enabled: bool,
        internal_reasoning_enabled: bool,
        few_shot_prompting_enabled: bool,
        interactive_mode: bool,
        current_step: Optional['ExecutionStep'] = None,
        current_plan: Optional['ExecutionPlan'] = None
    ) -> AsyncGenerator[str, None]:
        """
        Handle data extraction requests using Catalog-First Agent approach.

        1. CatalogAgenticRetriever searches catalog metadata (CHEAP)
        2. Agent decides which models to fetch (EXPENSIVE)
        3. SPARQL query is generated based on found models
        4. Query is sent to frontend for Comunica execution against Solid Pods
        """
        from .catalog import CatalogAgenticRetriever
        from .sparql_generation import generate_sparql_query

        logger.info(f"[Agent] Handling extraction with Catalog-First approach for: '{user_query[:50]}...'")

        # =====================================================================
        # CATALOG-FIRST AGENT: Search catalog and find relevant models
        # =====================================================================

        try:
            # 1. Emit initial status
            yield await format_sse_event({
                "message": "Searching the data catalog for relevant models...",
                "step_id": "catalog_search",
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # 2. Create Catalog Agent and retrieve models
            # Auth token from the user's Solid session. Used whenever one is
            # present: most of the dataspace is readable only to an authorised
            # WebID, and withholding the token would silently hide those pods.
            auth_token = self.context.solid_auth_token or None

            # Pass cached models from previous queries to avoid re-fetching
            cached_models = self.context.fetched_models_cache if self.context.fetched_models_cache else None
            cached_metadata = self.context.fetched_models_metadata if self.context.fetched_models_metadata else None

            if cached_models:
                logger.info(f"[Agent] Passing {len(cached_models)} cached models to retriever")

            # Pass cached catalog entries to avoid reloading 55 entries
            cached_catalog_entries = self.context.catalog_entries_cache if self.context.catalog_entries_cache else None
            if cached_catalog_entries:
                logger.info(f"[Agent] Passing {len(cached_catalog_entries)} cached catalog entries to retriever")

            retriever = CatalogAgenticRetriever(
                llm=self.llm,
                max_steps=settings.catalog_agent_max_steps,
                catalog_api_url=settings.catalog_api_url,
                auth_token=auth_token,
                pre_fetched_models=cached_models,
                pre_fetched_metadata=cached_metadata,
                conversation_history=self.context.conversation_history,
                catalog_search_history=self.context.catalog_search_history,
                pre_loaded_catalog_entries=cached_catalog_entries,
            )

            # Run the agentic retrieval
            retrieval_result = await retriever.retrieve_async(user_query, verbose=False)

            # Cache catalog entries for next request (avoid reloading 55 entries)
            loaded_entries = retriever.get_catalog_entries()
            if loaded_entries and not self.context.catalog_entries_cache:
                self.context.catalog_entries_cache = loaded_entries
                logger.info(f"[Agent] Cached {len(loaded_entries)} catalog entries for future requests")

            # Check if models were found
            if not retrieval_result.success or not retrieval_result.selected_models:
                yield await format_sse_event({
                    "message": f"No suitable models found. Reasoning: {retrieval_result.reasoning}",
                    "step_id": "no_models_found",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            selected_models = retrieval_result.selected_models
            model_contents = retrieval_result.model_contents

            # === Save newly fetched models and searches to cache for future queries ===
            for step in retrieval_result.steps:
                if step.tool == "fetch_model" and step.tool_result and step.tool_result.success:
                    model_id = step.tool_input.get("identifier", "")
                    data = step.tool_result.data
                    # Only cache if not already from cache
                    if model_id and data and not data.get("from_cache"):
                        content = data.get("content", "")
                        if content:
                            self.context.fetched_models_cache[model_id] = content
                            self.context.fetched_models_metadata[model_id] = {
                                "title": data.get("title", model_id),
                                "data_url": data.get("data_url"),
                                "classes": data.get("classes", []),
                            }
                            logger.info(f"[Agent] Cached model for future queries: {model_id}")

                # Also save catalog searches to history for future context
                elif step.tool == "search_catalog" and step.tool_result and step.tool_result.success:
                    search_query = step.tool_input.get("query", "")
                    search_results = step.tool_result.data.get("results", [])
                    if search_query and search_results:
                        self.context.catalog_search_history.append({
                            "query": search_query,
                            "timestamp": self.request_ts,
                            "total_found": len(search_results),
                            "results": search_results
                        })
                        logger.info(f"[Agent] Saved catalog search: '{search_query}' -> {len(search_results)} results")

            # Emit found models
            yield await format_sse_event({
                "message": f"Found {len(selected_models)} relevant models",
                "step_id": "models_found",
                "selected_models": selected_models,
                "fetch_count": retrieval_result.fetch_count,
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            logger.info(f"[Agent] Catalog retrieval completed: {len(selected_models)} models, "
                       f"{retrieval_result.fetch_count} fetches, {len(retrieval_result.steps)} steps")

            # 3. Prepare model content for SPARQL generation
            if not model_contents:
                yield await format_sse_event({
                    "message": "No model content available for SPARQL generation",
                    "step_id": "no_model_content",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            # Combine model contents
            combined_model_info = "\n\n".join([
                f"=== Model: {model_id} ===\n{content[:3000]}..."
                if len(content) > 3000 else f"=== Model: {model_id} ===\n{content}"
                for model_id, content in model_contents.items()
            ])

            # Store model info in context
            self.context.last_data_sources = selected_models
            self.context.model_info_blocks = combined_model_info

            # 4. Generate SPARQL query
            yield await format_sse_event({
                "message": "Generating the SPARQL query...",
                "step_id": "generating_sparql",
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # Work out the query by querying. A semantic model describes the
            # shape of the data, not its contents, so a query written from the
            # question alone frequently misses - a filter guessed from German
            # wording will not match data written in English. The agent runs as
            # many queries as it needs against the loaded datasets, sees each
            # result, and stops when it is satisfied.
            from .query_exploration import explore

            progress: List[str] = []

            async def note_step(number: int, thought: str) -> None:
                progress.append(f"{number}. {thought}" if thought else f"Query {number}")

            exploration = await explore(
                user_query=user_query,
                dataset_urls=[ds.url for ds in retrieval_result.dataset_urls],
                model_content=combined_model_info,
                llm=self.llm,
                auth_token=auth_token,
                on_step=note_step,
            )

            for line in progress:
                yield await format_sse_event({
                    "message": line,
                    "step_id": "query_exploration",
                    "request_timestamp": self.request_ts
                }, "pipeline_update")

            if not exploration.query:
                yield await format_sse_event({
                    "message": exploration.message or "No query returned matching data.",
                    "step_id": "sparql_generation_failed",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            sparql_query = exploration.query
            self.context.last_sparql_query = sparql_query
            self.context.exploration_summary = exploration.message
            self.context.exploration_step_count = len(exploration.steps)

            yield await format_sse_event({
                "message": f"Query settled after {len(exploration.steps)} attempt(s)",
                "step_id": "sparql_generated",
                "sparql_query": sparql_query,
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # 5. Send query to frontend for Comunica execution against Solid Pods
            # Convert dataset_urls to list of dicts for JSON serialization
            dataset_urls_for_frontend = [
                {
                    "url": ds.url,
                    "title": ds.title,
                    "identifier": ds.identifier
                }
                for ds in retrieval_result.dataset_urls
            ]

            if not dataset_urls_for_frontend:
                yield await format_sse_event({
                    "message": "No dataset URLs available for Comunica execution",
                    "step_id": "no_dataset_urls",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            logger.info(f"[Agent] Sending comunica_execution_required event with {len(dataset_urls_for_frontend)} dataset URLs")

            # Store context for when results come back and for follow-up queries
            # This must happen BEFORE yielding the event so it's available when event_generator receives it
            self.context.last_sparql_query = sparql_query
            self.context.last_data_sources = selected_models
            self.context.last_dataset_urls = dataset_urls_for_frontend  # Save for follow-up queries

            # Set step status and plan BEFORE yielding so execute_plan can pause properly
            # and event_generator can store the plan for /continue-plan endpoint
            if current_step is not None:
                current_step.status = "awaiting_comunica"
                logger.info(f"[Agent] Step {current_step.step_number} set to awaiting_comunica")
            if current_plan is not None:
                self.context.current_plan = current_plan
                logger.info(f"[Agent] Stored current_plan {current_plan.plan_id} for Comunica resumption")

            # Send comunica_execution_required event - frontend will execute via Comunica
            yield await format_sse_event({
                "sparql_query": sparql_query,
                "dataset_urls": dataset_urls_for_frontend,
                "selected_models": selected_models,
                "session_id": self.request_ts,
                "user_query": user_query,
                "request_timestamp": self.request_ts
            }, "comunica_execution_required")

            logger.info(f"[Agent] Comunica execution requested for {len(dataset_urls_for_frontend)} datasets")

        except Exception as e:
            logger.error(f"[Agent] Error in Catalog-First extraction: {e}", exc_info=True)
            yield await format_sse_event({
                "message": f"Data extraction failed: {str(e)}",
                "step_id": "extraction_error",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")

    async def _handle_follow_up(
        self,
        user_query: str,
        db_session,
        settings,
        agentic_reasoning_enabled: bool,
        internal_reasoning_enabled: bool,
        few_shot_prompting_enabled: bool,
        interactive_mode: bool,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handle follow-up queries using cached model information.

        Does NOT perform new catalog search - uses previously found models
        to generate a modified SPARQL query, then sends it to frontend for Comunica execution.
        """
        from .sparql_generation import generate_sparql_query

        logger.info(f"[Agent] Handling follow-up for: '{user_query[:50]}...'")

        # Check if we have previous context
        if not self.context.model_info_blocks and not self.context.last_data_sources:
            yield await format_sse_event({
                "message": "No earlier data extraction found. Please start with a new request.",
                "step_id": "follow_up_no_context",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")
            return

        try:
            # 1. Emit status
            yield await format_sse_event({
                "message": "Handling the follow-up with the models already loaded...",
                "step_id": "follow_up_processing",
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # 2. Build context for SPARQL generation including previous query
            previous_query_context = ""
            if self.context.last_sparql_query:
                previous_query_context = f"\n\nPrevious SPARQL query:\n{self.context.last_sparql_query}"

            # Combine with follow-up request
            combined_query = f"{user_query}{previous_query_context}"
            model_info = self.context.model_info_blocks or ""

            # 3. Generate new SPARQL query
            yield await format_sse_event({
                "message": "Generating the adjusted SPARQL query...",
                "step_id": "generating_follow_up_sparql",
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            sparql_result = await generate_sparql_query(
                user_query=combined_query,
                model_info_blocks=model_info,
                model_check_hints="",
                llm_instance=self.llm,
                internal_reasoning_enabled=agentic_reasoning_enabled,
                few_shot_prompting_enabled=few_shot_prompting_enabled,
                request_id=self.request_ts
            )

            if not sparql_result or not sparql_result.get('sparql_query'):
                yield await format_sse_event({
                    "message": "SPARQL generation for the follow-up failed",
                    "step_id": "follow_up_sparql_failed",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            sparql_query = sparql_result['sparql_query']
            self.context.last_sparql_query = sparql_query

            yield await format_sse_event({
                "message": "Follow-up SPARQL query generated",
                "step_id": "follow_up_sparql_generated",
                "sparql_query": sparql_query,
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # 4. Send query to frontend for Comunica execution
            # Use previously stored dataset URLs
            dataset_urls = self.context.last_dataset_urls

            if not dataset_urls:
                yield await format_sse_event({
                    "message": "No dataset URLs in context for the follow-up Comunica execution",
                    "step_id": "follow_up_no_dataset_urls",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            logger.info(f"[Agent] Sending follow-up comunica_execution_required event with {len(dataset_urls)} dataset URLs")

            # Set step status and plan BEFORE yielding so execute_plan can pause properly
            # and event_generator can store the plan for /continue-plan endpoint
            current_step = kwargs.get("current_step")
            current_plan = kwargs.get("current_plan")
            if current_step is not None:
                current_step.status = "awaiting_comunica"
                logger.info(f"[Agent] Follow-up step {current_step.step_number} set to awaiting_comunica")
            if current_plan is not None:
                self.context.current_plan = current_plan
                logger.info(f"[Agent] Stored current_plan {current_plan.plan_id} for follow-up Comunica resumption")

            # Send comunica_execution_required event - frontend will execute via Comunica
            yield await format_sse_event({
                "sparql_query": sparql_query,
                "dataset_urls": dataset_urls,
                "selected_models": self.context.last_data_sources,
                "session_id": self.request_ts,
                "user_query": user_query,
                "request_timestamp": self.request_ts
            }, "comunica_execution_required")

            logger.info(f"[Agent] Follow-up Comunica execution requested")

        except Exception as e:
            logger.error(f"[Agent] Error in follow-up handler: {e}", exc_info=True)
            yield await format_sse_event({
                "message": f"The follow-up failed: {str(e)}",
                "step_id": "follow_up_error",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")

    async def _handle_corpus_info(
        self,
        user_query: str,
        db_session,
        settings,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handle corpus information requests using the Remote Catalog.
        Uses the UnifiedCatalogAgent to query the Solid Pod catalog.
        NO local data is used - everything comes from the remote catalog.
        """
        from .catalog import UnifiedCatalogAgent
        from .utils import stream_message_fake

        logger.info(f"[Agent] Handling corpus info via Remote Catalog for: '{user_query[:50]}...'")

        try:
            # Announce catalog query
            yield await format_sse_event({
                "message": "Searching the remote data catalog...",
                "step_id": "corpus_info_searching",
                "request_timestamp": self.request_ts
            }, "pipeline_update")

            # Create UnifiedCatalogAgent with catalog settings
            catalog_api_url = getattr(settings, 'catalog_api_url', None)
            auth_token = self.context.solid_auth_token if hasattr(self.context, 'solid_auth_token') else None

            # Pass cached catalog entries to avoid reloading 55 entries
            cached_catalog_entries = self.context.catalog_entries_cache if self.context.catalog_entries_cache else None
            if cached_catalog_entries:
                logger.info(f"[Agent] Passing {len(cached_catalog_entries)} cached catalog entries to UnifiedCatalogAgent")

            agent = UnifiedCatalogAgent(
                llm=self.llm,
                graphdb_url=getattr(settings, 'graphdb_base_url', ''),
                workspace_id=self.workspace_id,
                auth_token=auth_token,
                catalog_api_url=catalog_api_url,
                max_steps=10,
                conversation_history=self.context.conversation_history,
                catalog_search_history=self.context.catalog_search_history,
                pre_loaded_catalog_entries=cached_catalog_entries,
            )

            # Use get_corpus_overview tool directly for simple corpus info requests
            corpus_result = await agent.tools.get_corpus_overview_async()

            # Cache catalog entries for next request (avoid reloading 55 entries)
            loaded_entries = agent.get_catalog_entries()
            if loaded_entries and not self.context.catalog_entries_cache:
                self.context.catalog_entries_cache = loaded_entries
                logger.info(f"[Agent] Cached {len(loaded_entries)} catalog entries for future requests")

            if not corpus_result.success:
                async for event in stream_message_fake(
                    message=f"Could not fetch the catalog: {corpus_result.message}",
                    sender="dina",
                    step_id="corpus_info_error",
                    request_timestamp=self.request_ts,
                    delay_between_chars=0.01,
                    delay_between_words=0.05
                ):
                    yield event
                return

            # Extract data from result
            total_datasets = corpus_result.data.get("total_datasets", 0)
            themes = corpus_result.data.get("themes", {})
            datasets = corpus_result.data.get("datasets", [])

            # Emit catalog info event
            yield await format_sse_event({
                "total_datasets": total_datasets,
                "themes": themes,
                "datasets_preview": datasets[:10],
                "step_id": "corpus_info_result"
            }, "corpus_info")

            # If user query is specific, also search the catalog
            search_results = []
            if len(user_query.split()) > 2:  # More than a bare "which data"
                # Always perform search - the Agent gets catalog_search_history as context
                # and can decide itself whether to use previous results
                search_result = await agent.tools.search_catalog_async(
                    query=user_query,
                    top_k=10
                )

                if search_result.success and search_result.data.get("results"):
                    search_results = search_result.data.get("results", [])

                    # Save to history - Agent uses this as context for future queries
                    self.context.catalog_search_history.append({
                        "query": user_query,
                        "timestamp": self.request_ts,
                        "total_found": len(search_results),
                        "results": search_results
                    })
                    logger.info(f"[Agent] Saved catalog search for '{user_query}': {len(search_results)} results")

                    yield await format_sse_event({
                        "total_found": search_result.data.get("total_found"),
                        "results": search_results[:5],
                        "step_id": "corpus_search_result"
                    }, "search_results")

            # Generate prose response - pass search results for specific queries
            response = await self._generate_catalog_corpus_info_response(
                user_query=user_query,
                total_datasets=total_datasets,
                themes=themes,
                datasets=datasets,
                search_results=search_results
            )

            # Stream the response
            async for event in stream_message_fake(
                message=response,
                sender="dina",
                step_id="corpus_info_text",
                request_timestamp=self.request_ts,
                delay_between_chars=0.01,
                delay_between_words=0.04
            ):
                yield event

            # Close agent resources
            await agent.close()

        except Exception as e:
            logger.error(f"[Agent] Error in corpus info handler: {e}", exc_info=True)
            async for event in stream_message_fake(
                message=f"Something went wrong querying the catalog: {str(e)}",
                sender="dina",
                step_id="corpus_info_error",
                request_timestamp=self.request_ts,
                delay_between_chars=0.01,
                delay_between_words=0.05
            ):
                yield event

    async def _generate_catalog_corpus_info_response(
        self,
        user_query: str,
        total_datasets: int,
        themes: Dict[str, int],
        datasets: List[Dict],
        search_results: List[Dict] = None
    ) -> str:
        """Generate a prose response describing the catalog contents.

        If search_results are provided (for specific queries), prioritize those
        over generic catalog information to avoid hallucination.
        """
        themes_text = ", ".join([f"{theme}: {count}" for theme, count in themes.items()])

        # Check if this is a specific query with search results
        if search_results and len(search_results) > 0:
            # Use ONLY the search results for specific queries
            results_text = "\n".join([
                f"- {r.get('title', r.get('model_name', 'Unknown'))}: {r.get('description', '')[:150]}"
                for r in search_results
            ])

            prompt = f"""Answer the user's question using ONLY the catalog search
results below.

QUESTION: "{user_query}"

DATASETS FOUND ({len(search_results)} matches):
{results_text}

RULES:
- Describe only the datasets listed above.
- Do not invent additional datasets or figures.
- If little was found, say so plainly.
- Name the actual dataset titles.

Keep the answer short and precise.
IMPORTANT: Reply in {describe_reply_language(user_query)}."""

        else:
            # Generic catalog overview (no specific search)
            sample_datasets = datasets[:10]
            datasets_text = "\n".join([
                f"- {d.get('title', d.get('model_name', 'Unknown'))}: {d.get('description', '')[:100]}"
                for d in sample_datasets
            ])

            prompt = f"""Give an overview of the data catalog using ONLY the
information below.

QUESTION: "{user_query}"

CATALOG STATISTICS:
- Datasets in total: {total_datasets}
- Categories: {themes_text}

SAMPLE DATASETS (first 10):
{datasets_text}

RULES:
- Use only the figures and categories given above.
- Do not invent additional statistics or datasets.
- Describe only what is actually listed.

Keep the answer short and helpful.
IMPORTANT: Reply in {describe_reply_language(user_query)}."""

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"[Agent] Error generating corpus response: {e}")
            # Fallback response
            if search_results:
                titles = [r.get('title', r.get('model_name', '?')) for r in search_results[:5]]
                return f"Your request matched {len(search_results)} datasets: {', '.join(titles)}."
            return f"The data catalog holds {total_datasets} datasets across {len(themes)} categories: {themes_text}."

    async def _generate_model_description_from_triples(
        self,
        model_name: str,
        all_triples: str,
        user_query: str
    ) -> str:
        """Generate a comprehensive human-readable description of what data a model contains"""

        # Clean up model name for display
        display_name = model_name.replace('.ttl', '').replace('_', ' ')

        # Use all triples for comprehensive analysis (limit to reasonable size for LLM)
        # Truncate if too long but keep enough context
        max_chars = 8000
        triples_text = all_triples[:max_chars] if len(all_triples) > max_chars else all_triples

        prompt = f"""Study this semantic model and describe, in plain language, what data it holds.

File name: {display_name}
User request: {user_query}

THE COMPLETE SEMANTIC MODEL:
{triples_text}

Write a detailed description of three to five sentences covering:
1. What kind of data or entities it contains (accidents, materials, processes, ...)
2. Which concrete attributes are recorded (date, location, quantity, ...)
3. Any geographic scope, time range or other limits you can make out
4. What questions this data could answer

Be concrete: name the actual details from the model (say "Brandenburg", not "a federal state").
Write it as flowing prose, not as a bullet list.
IMPORTANT: Reply in {describe_reply_language(user_query)}."""

        try:
            description = await asyncio.to_thread(self.llm.invoke, prompt)
            return description.strip()[:500]  # Allow longer description
        except Exception as e:
            logger.warning(f"Could not generate description for {model_name}: {e}")
            return ""

    async def _generate_corpus_info_response(
        self,
        user_query: str,
        sorted_models: List[tuple],
        model_descriptions: Dict[str, str],
        total_files: int
    ) -> str:
        """Generate a coherent prose response about the relevant files"""

        num_relevant = len(sorted_models)
        num_other = total_files - num_relevant

        # Build context for LLM
        files_info = []
        for model_name, data in sorted_models:
            display_name = model_name.replace('.ttl', '').replace('_', ' ')
            description = model_descriptions.get(model_name, '')
            files_info.append(f"- {display_name}: {description}")

        files_context = "\n".join(files_info)

        prompt = f"""Answer the user's question about available files in natural prose.

User request: "{user_query}"

Relevant files found ({num_relevant} of {total_files} in the workspace):
{files_context}

Write a friendly, informative answer that:
1. Speaks directly to what was asked
2. Describes the relevant files and what is in them, with the file names in bold
3. Closes by mentioning briefly how many other files were not relevant

It should read like a helpful assistant, not a technical inventory.
Answer directly - no preamble such as "Here is the answer".
IMPORTANT: Reply in {describe_reply_language(user_query)}."""

        try:
            response = await asyncio.to_thread(self.llm.invoke, prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating corpus info response: {e}")
            # Fallback to simple response
            parts = [f"Your request \"{user_query}\" matched {num_relevant} relevant file(s):\n"]
            for model_name, data in sorted_models:
                display_name = model_name.replace('.ttl', '').replace('_', ' ')
                desc = model_descriptions.get(model_name, '')
                parts.append(f"**{display_name}**: {desc}")
            if num_other > 0:
                parts.append(f"\n{num_other} further files in the workspace were not relevant here.")
            return "\n".join(parts)

    async def _handle_visualization(
        self,
        user_query: str,
        db_session,
        settings,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handle visualization requests - generate matplotlib code and execute it.
        Uses lazy loading to fetch full results from cache if needed.
        Supports explicit result references via uses_result in ExecutionStep.
        """
        from .utils import stream_message_fake

        # Get current step for result reference
        current_step: Optional[ExecutionStep] = kwargs.get('current_step')
        uses_result = current_step.uses_result if current_step else None

        logger.info(f"[Agent] Handling visualization for: '{user_query[:50]}...'")
        if uses_result:
            logger.info(f"[Agent] Visualization uses explicit result reference: {uses_result}")

        # Determine which results to use
        target_entry: Optional[ResultsHistoryEntry] = None
        if uses_result:
            target_entry = self.context.get_result_by_id(uses_result)
            if target_entry:
                logger.info(f"[Agent] Using result entry: {target_entry.entry_id} - {target_entry.description}")
            else:
                logger.warning(f"[Agent] Result entry not found: {uses_result}, falling back to latest")

        # Debug: Log current context state
        if target_entry:
            result_info = {
                "type": "history",
                "entry_id": target_entry.entry_id,
                "total_count": target_entry.total_count,
                "variables": target_entry.variables
            }
        else:
            result_info = self.context.get_results_for_llm()

        logger.info(f"[Agent] Visualization context state:")
        logger.info(f"  - session_id: {self.context.session_id}")
        logger.info(f"  - results type: {result_info.get('type', 'none')}")
        logger.info(f"  - total_count: {result_info.get('total_count', 0)}")
        if target_entry:
            logger.info(f"  - using entry: {target_entry.entry_id}")
            logger.info(f"  - entry variables: {target_entry.variables}")
        else:
            logger.info(f"  - last_sparql_variables: {self.context.last_sparql_variables}")
        logger.info(f"  - last_data_sources: {self.context.last_data_sources}")

        # Check if we have data to visualize (SPARQL results OR calculation results)
        has_sparql_data = target_entry is not None or self.context.has_results()
        has_calculation_data = self.context.last_calculation_results is not None

        if not has_sparql_data and not has_calculation_data:
            logger.warning(f"[Agent] No data available for visualization!")
            yield await format_sse_event({
                "message": "There is no data to chart yet. Run a data extraction or a calculation first.",
                "step_id": "visualization_no_data",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")
            return

        # Determine data source: prefer calculation results if available (for chaining)
        use_calculation_results = has_calculation_data and not target_entry

        if use_calculation_results:
            logger.info("[Agent] Using calculation results for visualization (chaining)")

        # Stream initial message
        async for event in stream_message_fake(
            message="Building the chart...",
            sender="dina",
            step_id="visualization_generating",
            request_timestamp=self.request_ts,
            delay_between_chars=0.02,
            delay_between_words=0.1
        ):
            yield event

        try:
            # Get sample data and variables for code generation
            if use_calculation_results:
                # Use calculation results (from previous DATA_CALCULATION step)
                calc_table = self.context.last_calculation_results.get('table', [])
                sample_data = calc_table[:5]
                variables = list(calc_table[0].keys()) if calc_table else []
                # For calculation results, the data structure is simpler (direct values, not SPARQL format)
                # We need to convert to visualization-friendly format
                full_results = calc_table
                logger.info(f"[Agent] Using {len(calc_table)} calculation result rows for visualization")
            elif target_entry:
                # Use data from specific history entry
                sample_data = target_entry.sample[:5]
                variables = target_entry.variables
                full_results = await self.context.get_full_results(target_entry.entry_id)
            elif self.context.last_sparql_results:
                sample_data = self.context.last_sparql_results[:5]
                variables = self.context.last_sparql_variables or []
                full_results = await self.context.get_full_results()
            elif self.context.results_ref:
                sample_data = self.context.results_ref.sample
                variables = self.context.results_ref.variables
                full_results = await self.context.get_full_results()
            else:
                sample_data = []
                variables = []
                full_results = []

            # Generate visualization code
            code = await self._generate_visualization_code(
                user_query=user_query,
                variables=variables,
                sample_data=sample_data,
                is_calculation_data=use_calculation_results
            )

            if not full_results:
                logger.error("[Agent] Failed to load full results for visualization")
                yield await format_sse_event({
                    "message": "Could not load the full data set for the chart.",
                    "step_id": "visualization_data_error",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            logger.info(f"[Agent] Loaded {len(full_results)} results for visualization")

            # Execute the code and get image
            image_base64 = await self._execute_visualization_code(
                code=code,
                data=full_results
            )

            # Stream success message
            async for event in stream_message_fake(
                message="Here is the chart:",
                sender="dina",
                step_id="visualization_created",
                request_timestamp=self.request_ts,
                delay_between_chars=0.02,
                delay_between_words=0.1
            ):
                yield event

            # Send visualization result
            yield await format_sse_event({
                "message": "",
                "step_id": "visualization_result",
                "response_type": "visualization",
                "visualization_code": code,
                "visualization_image_base64": image_base64,
                "request_timestamp": self.request_ts
            }, "visualization_result")

        except Exception as e:
            logger.error(f"[Agent] Error in visualization handler: {e}", exc_info=True)
            yield await format_sse_event({
                "message": f"Charting failed: {str(e)}",
                "step_id": "visualization_error",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")

    async def _generate_visualization_code(
        self,
        user_query: str,
        variables: List[str],
        sample_data: List[Dict],
        is_calculation_data: bool = False
    ) -> str:
        """Generate matplotlib visualization code using LLM"""

        # Format sample data for prompt
        sample_str = json.dumps(sample_data, indent=2, ensure_ascii=False)

        # If this is calculation data, add hint about simpler data structure
        if is_calculation_data:
            data_hint = """
IMPORTANT: this data came out of an earlier calculation, so its structure is SIMPLER!
The values are accessible DIRECTLY (e.g. d['Product'], d['CO2']) rather than via d.get('var', {}).get('value', '')
"""
            prompt = VISUALIZATION_GENERATION_PROMPT.format(
                variables=", ".join(variables),
                sample_data=sample_str,
                user_query=user_query
            )
            # Insert the hint after the sample data
            prompt = prompt.replace("USER REQUEST:", f"{data_hint}\nUSER REQUEST:")
        else:
            prompt = VISUALIZATION_GENERATION_PROMPT.format(
                variables=", ".join(variables),
                sample_data=sample_str,
                user_query=user_query
            )

        response = await asyncio.to_thread(self.llm.invoke, prompt)

        # Extract code from response
        code = response.strip()

        # Remove markdown code blocks if present
        if "```python" in code:
            code = code.split("```python")[1]
            if "```" in code:
                code = code.split("```")[0]
        elif "```" in code:
            code = code.split("```")[1]
            if "```" in code:
                code = code.split("```")[0]

        return code.strip()

    async def _execute_visualization_code(self, code: str, data: List[Dict]) -> str:
        """Execute matplotlib code safely and return base64 PNG image"""
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt

        # Remove import statements from generated code - modules are already provided
        code_lines = code.split('\n')
        cleaned_lines = []
        for line in code_lines:
            stripped = line.strip()
            # Skip import statements - we provide these modules directly
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue
            cleaned_lines.append(line)
        code = '\n'.join(cleaned_lines)

        logger.info(f"[Agent] Executing visualization code (cleaned):\n{code[:500]}...")

        # Sandbox environment with restricted globals
        # Include DINa color palette for consistent branding
        safe_globals = {
            'plt': plt,
            'matplotlib': matplotlib,
            'data': data,
            # DINa Color Palette
            'DINA_BLUE': '#164475',
            'DINA_ORANGE': '#C6712F',
            'DINA_COLORS': ['#164475', '#C6712F', '#5a87be', '#d4894f', '#0f3159', '#a85d26'],
            'DINA_PRIMARY': '#164475',
            'DINA_ACCENT': '#C6712F',
            '__builtins__': {
                'len': len,
                'range': range,
                'list': list,
                'dict': dict,
                'str': str,
                'int': int,
                'float': float,
                'sum': sum,
                'min': min,
                'max': max,
                'sorted': sorted,
                'zip': zip,
                'enumerate': enumerate,
                'round': round,
                'abs': abs,
                'set': set,
                'tuple': tuple,
                'bool': bool,
                'map': map,
                'filter': filter,
                'any': any,
                'all': all,
                'isinstance': isinstance,
                'type': type,
                'True': True,
                'False': False,
                'None': None,
                'print': lambda *args, **kwargs: None,  # Suppress prints
            }
        }

        rejected = screen_generated_code(code)
        if rejected:
            raise ValueError(
                f"Generated visualization code was rejected: it uses '{rejected}'."
            )

        try:
            # Clear any existing figures
            plt.close('all')

            # Execute the code
            exec(code, safe_globals)

            # Save figure to bytes
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            buf.seek(0)
            image_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close('all')

            return image_base64

        except Exception as e:
            plt.close('all')
            raise ValueError(f"Chart generation failed: {str(e)}")

    async def _handle_calculation(
        self,
        user_query: str,
        db_session,
        settings,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handle calculation requests - generate Python code for calculations and execute it.
        Uses lazy loading to fetch full results from cache if needed.
        Stores results for potential chaining with visualization.
        Supports explicit result references via uses_result in ExecutionStep.
        """
        from .utils import stream_message_fake

        # Get current step for result reference
        current_step: Optional[ExecutionStep] = kwargs.get('current_step')
        uses_result = current_step.uses_result if current_step else None

        logger.info(f"[Agent] Handling calculation for: '{user_query[:50]}...'")
        if uses_result:
            logger.info(f"[Agent] Calculation uses explicit result reference: {uses_result}")

        # Determine which results to use
        target_entry: Optional[ResultsHistoryEntry] = None
        if uses_result:
            target_entry = self.context.get_result_by_id(uses_result)
            if target_entry:
                logger.info(f"[Agent] Using result entry: {target_entry.entry_id} - {target_entry.description}")
            else:
                logger.warning(f"[Agent] Result entry not found: {uses_result}, falling back to latest")

        # Check if we have data to calculate
        has_data = target_entry is not None or self.context.has_results()
        if not has_data:
            logger.warning(f"[Agent] No SPARQL results available for calculation!")
            yield await format_sse_event({
                "message": "There is no data to compute on yet. Run a data extraction first.",
                "step_id": "calculation_no_data",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")
            return

        # Stream initial message
        async for event in stream_message_fake(
            message="Crunching the numbers...",
            sender="dina",
            step_id="calculation_generating",
            request_timestamp=self.request_ts,
            delay_between_chars=0.02,
            delay_between_words=0.1
        ):
            yield event

        try:
            # Get sample data and variables for code generation
            if target_entry:
                sample_data = target_entry.sample[:5]
                variables = target_entry.variables
            elif self.context.last_sparql_results:
                sample_data = self.context.last_sparql_results[:5]
                variables = self.context.last_sparql_variables or []
            elif self.context.results_ref:
                sample_data = self.context.results_ref.sample
                variables = self.context.results_ref.variables
            else:
                sample_data = []
                variables = []

            # Generate calculation code
            code = await self._generate_calculation_code(
                user_query=user_query,
                variables=variables,
                sample_data=sample_data
            )

            # Get full results for execution
            if target_entry:
                full_results = await self.context.get_full_results(target_entry.entry_id)
            else:
                full_results = await self.context.get_full_results()

            if not full_results:
                logger.error("[Agent] Failed to load full results for calculation")
                yield await format_sse_event({
                    "message": "Could not load the full data set for the calculation.",
                    "step_id": "calculation_data_error",
                    "is_error": True,
                    "request_timestamp": self.request_ts
                }, "pipeline_error")
                return

            logger.info(f"[Agent] Loaded {len(full_results)} results for calculation")

            # Execute the code and get results
            calculation_result = await self._execute_calculation_code(
                code=code,
                data=full_results
            )

            # Store calculation results for potential chaining with visualization
            self.context.last_calculation_results = calculation_result
            self.context.last_calculation_code = code

            # Stream success message
            async for event in stream_message_fake(
                message="Calculation complete:",
                sender="dina",
                step_id="calculation_completed",
                request_timestamp=self.request_ts,
                delay_between_chars=0.02,
                delay_between_words=0.1
            ):
                yield event

            # Send calculation result
            yield await format_sse_event({
                "message": "",
                "step_id": "calculation_result",
                "response_type": "calculation",
                "calculation_code": code,
                "calculation_summary": calculation_result.get('summary', {}),
                "calculation_table": calculation_result.get('table', []),
                "calculation_metadata": calculation_result.get('metadata', {}),
                "calculation_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                "request_timestamp": self.request_ts
            }, "calculation_result")

        except Exception as e:
            logger.error(f"[Agent] Error in calculation handler: {e}", exc_info=True)
            yield await format_sse_event({
                "message": f"The calculation failed: {str(e)}",
                "step_id": "calculation_error",
                "is_error": True,
                "request_timestamp": self.request_ts
            }, "pipeline_error")

    async def _generate_calculation_code(
        self,
        user_query: str,
        variables: List[str],
        sample_data: List[Dict]
    ) -> str:
        """Generate Python calculation code using LLM"""

        # Format sample data for prompt
        sample_str = json.dumps(sample_data, indent=2, ensure_ascii=False)

        # Build context info for ESG-specific calculations
        context_info = self._build_calculation_context(variables, sample_data)

        prompt = CALCULATION_GENERATION_PROMPT.format(
            variables=", ".join(variables),
            sample_data=sample_str,
            user_query=user_query,
            context_info=context_info
        )

        response = await asyncio.to_thread(self.llm.invoke, prompt)

        # Extract code from response
        code = response.strip()

        # Remove markdown code blocks if present
        if "```python" in code:
            code = code.split("```python")[1]
            if "```" in code:
                code = code.split("```")[0]
        elif "```" in code:
            code = code.split("```")[1]
            if "```" in code:
                code = code.split("```")[0]

        return code.strip()

    def _build_calculation_context(self, variables: List[str], sample_data: List[Dict]) -> str:
        """Build context information for calculation code generation"""
        context_parts = []

        # Detect numeric variables
        numeric_vars = []
        for var in variables:
            if sample_data:
                sample_val = sample_data[0].get(var, {}).get('value', '')
                try:
                    float(sample_val)
                    numeric_vars.append(var)
                except (ValueError, TypeError):
                    pass

        if numeric_vars:
            context_parts.append(f"Numeric variables: {', '.join(numeric_vars)}")

        # ESG domain hints
        esg_keywords = {
            'co2': 'CO2 emissions / carbon footprint',
            'emission': 'emission values',
            'energy': 'energy consumption',
            'energie': 'energy consumption',
            'water': 'water consumption',
            'wasser': 'water consumption',
            'waste': 'waste volume',
            'abfall': 'waste volume',
            'material': 'material input',
            'transport': 'transport emissions',
            'gewicht': 'weight / mass',
            'weight': 'weight / mass',
            'menge': 'a quantity',
            'quantity': 'a quantity'
        }

        for var in variables:
            var_lower = var.lower()
            for keyword, description in esg_keywords.items():
                if keyword in var_lower:
                    context_parts.append(f"Variable '{var}' appears to hold {description}")
                    break

        return "\n".join(context_parts) if context_parts else "No special context available"

    async def _execute_calculation_code(self, code: str, data: List[Dict]) -> Dict[str, Any]:
        """Execute Python calculation code safely and return structured results"""
        import math
        import statistics

        # Remove import statements from generated code - modules are already provided
        code_lines = code.split('\n')
        cleaned_lines = []
        for line in code_lines:
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                continue
            cleaned_lines.append(line)
        code = '\n'.join(cleaned_lines)

        logger.info(f"[Agent] Executing calculation code (cleaned):\n{code[:500]}...")

        # Sandbox environment - extended for calculations
        safe_globals = {
            'data': data,
            '__builtins__': {
                # Basic types
                'len': len, 'range': range, 'list': list, 'dict': dict,
                'str': str, 'int': int, 'float': float, 'bool': bool,
                'tuple': tuple, 'set': set,
                # Math operations
                'sum': sum, 'min': min, 'max': max, 'abs': abs, 'round': round,
                'pow': pow, 'divmod': divmod,
                # Iteration
                'sorted': sorted, 'zip': zip, 'enumerate': enumerate,
                'map': map, 'filter': filter, 'reversed': reversed,
                # Logic
                'any': any, 'all': all, 'isinstance': isinstance, 'type': type,
                # Constants
                'True': True, 'False': False, 'None': None,
                # Suppress prints
                'print': lambda *args, **kwargs: None,
            },
            # Math module for advanced calculations
            'math': math,
            # Statistics for ESG calculations
            'statistics': statistics,
        }

        rejected = screen_generated_code(code)
        if rejected:
            raise ValueError(
                f"Generated calculation code was rejected: it uses '{rejected}'."
            )

        try:
            # Execute the code
            exec(code, safe_globals)

            # Extract the result
            calculation_result = safe_globals.get('calculation_result')

            if calculation_result is None:
                raise ValueError("Code did not produce 'calculation_result' variable")

            # Validate structure
            if not isinstance(calculation_result, dict):
                raise ValueError("calculation_result must be a dictionary")

            # Ensure required keys exist with defaults
            if 'summary' not in calculation_result:
                calculation_result['summary'] = {}
            if 'table' not in calculation_result:
                calculation_result['table'] = []
            if 'metadata' not in calculation_result:
                calculation_result['metadata'] = {}

            return calculation_result

        except Exception as e:
            raise ValueError(f"Calculation failed: {str(e)}")

    async def _handle_new_query(
        self,
        user_query: str,
        db_session,
        settings,
        agentic_reasoning_enabled: bool,
        internal_reasoning_enabled: bool,
        few_shot_prompting_enabled: bool,
        interactive_mode: bool,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Handle new query requests - reset context and start fresh extraction.
        """
        from .utils import stream_message_fake

        logger.info(f"[Agent] Starting new query session for: '{user_query[:50]}...'")

        # Reset context
        self.context.session_id = None
        self.context.last_sparql_results = None
        self.context.last_sparql_query = None
        self.context.last_sparql_variables = None
        self.context.last_data_sources = []
        self.context.model_info_blocks = None
        self.context.model_check_hints = None

        # Stream notification
        async for event in stream_message_fake(
            message="Starting a fresh data query...",
            sender="dina",
            step_id="new_query_starting",
            request_timestamp=self.request_ts,
            delay_between_chars=0.02,
            delay_between_words=0.1
        ):
            yield event

        # Forward to extraction handler
        async for event in self._handle_extraction(
            user_query=user_query,
            db_session=db_session,
            settings=settings,
            agentic_reasoning_enabled=agentic_reasoning_enabled,
            internal_reasoning_enabled=internal_reasoning_enabled,
            few_shot_prompting_enabled=few_shot_prompting_enabled,
            interactive_mode=interactive_mode
        ):
            yield event

    def _parse_sse_event(self, event_str: str) -> Optional[Dict]:
        """Parse SSE event string to extract data - handles multi-line JSON"""
        try:
            lines = event_str.strip().split('\n')
            data_lines = []
            in_data = False

            for line in lines:
                if line.startswith("data:"):
                    # Start collecting data
                    data_part = line[5:].strip()  # Everything after "data:"
                    if data_part:
                        data_lines.append(data_part)
                    in_data = True
                elif in_data and line.strip() and not line.startswith("event:") and not line.startswith("id:"):
                    # Continue collecting multi-line data
                    data_lines.append(line.strip())
                elif line.strip() == "":
                    # Empty line signals end of this event
                    in_data = False

            if data_lines:
                # Try to parse as single JSON first
                full_data = " ".join(data_lines)
                try:
                    return json.loads(full_data)
                except json.JSONDecodeError:
                    # Fallback: try just the first line
                    try:
                        return json.loads(data_lines[0])
                    except json.JSONDecodeError:
                        pass

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error in SSE event: {e}")
        except Exception as e:
            logger.debug(f"Could not parse SSE event: {e}")
        return None

    def update_context_from_session(self, session) -> None:
        """Update agent context from a ChatSession object"""
        self.context.session_id = str(session.id)
        self.context.last_data_sources = session.selected_models or []
        self.context.model_info_blocks = session.model_info_blocks
        self.context.model_check_hints = session.model_check_hints
        self.context.last_user_query = session.initial_query
