"""
Catalog-first agentic retriever - agent-driven retrieval over the DCAT catalog

STRATEGY: CATALOG FIRST, WITH THE AGENT IN CHARGE
1. The agent searches the catalog metadata (FREE)
2. The agent decides for itself which models to fetch (EXPENSIVE)
3. The agent inspects the content and judges whether more fetches are needed
"""

import json
import re
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union

from .tools import CatalogTools, ToolResult, CATALOG_TOOL_DESCRIPTIONS
from .cache import CacheStats

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT DATACLASSES
# =============================================================================
@dataclass
class AgentStep:
    """A single step taken by the agent."""
    thought: str
    tool: str
    tool_input: Dict[str, Any]
    tool_result: Optional[ToolResult] = None


@dataclass
class DatasetUrl:
    """The URL details Comunica needs in order to execute a query."""
    url: str
    title: str
    identifier: str

@dataclass
class AgentResult:
    """The agent's final result."""
    query: str
    steps: List[AgentStep] = field(default_factory=list)
    selected_models: List[str] = field(default_factory=list)
    model_contents: Dict[str, str] = field(default_factory=dict)  # identifier -> content
    dataset_urls: List[DatasetUrl] = field(default_factory=list)  # URLs for Comunica execution
    reasoning: str = ""
    success: bool = False
    fetch_count: int = 0
    cache_stats: Optional[CacheStats] = None


# =============================================================================
# CATALOG AGENTIC RETRIEVER
# =============================================================================
class CatalogAgenticRetriever:
    """
    Agent-driven catalog retriever.

    Working from the catalog metadata alone, the agent decides for itself which
    models are worth fetching.

    Token-based authentication is supported for Solid-protected resources.
    """

    def __init__(
        self,
        llm,  # Any LLM that has an invoke() method
        max_steps: int = 15,
        catalog_api_url: str = None,
        auth_token: str = None,
        pre_fetched_models: Optional[Dict[str, str]] = None,
        pre_fetched_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        catalog_search_history: Optional[List[Dict[str, Any]]] = None,
        pre_loaded_catalog_entries: Optional[List[Any]] = None,
    ):
        """
        Initialize the retriever.

        Args:
            llm: LLM instance with invoke() method (OllamaLLM, DeepSeekLLM, etc.)
            max_steps: Maximum agent steps
            catalog_api_url: Optional custom catalog API URL
            auth_token: Optional Solid/DPoP Access Token for authenticated requests
            pre_fetched_models: Dict of model_id -> content from previous queries (cached)
            pre_fetched_metadata: Dict of model_id -> metadata (title, classes, etc.) from cache
            conversation_history: Previous conversation messages from the session
            catalog_search_history: Previous catalog searches from the session
            pre_loaded_catalog_entries: Pre-loaded catalog entries to avoid reloading
        """
        self.llm = llm
        self.max_steps = max_steps
        self.decision_deadline = max_steps - 2
        self.tools = CatalogTools(
            catalog_api_url=catalog_api_url,
            auth_token=auth_token,
            pre_loaded_catalog_entries=pre_loaded_catalog_entries,
        )
        # Cache from previous queries - avoids re-fetching
        self.pre_fetched_models = pre_fetched_models or {}
        self.pre_fetched_metadata = pre_fetched_metadata or {}
        # Session context
        self._conversation_history = conversation_history or []
        self._catalog_search_history = catalog_search_history or []

    def set_auth_token(self, token: str) -> None:
        """Set the auth token used for authenticated requests."""
        self.tools.set_auth_token(token)

    def get_catalog_entries(self) -> List[Any]:
        """Return the loaded catalog entries so the session can cache them."""
        return self.tools.get_catalog_entries()

    def _build_system_prompt(self, current_step: int = 0) -> str:
        """Build the system prompt for the agent."""
        steps_remaining = self.max_steps - current_step
        deadline_warning = ""

        if steps_remaining <= 3:
            deadline_warning = f"""
!!! WARNING: ONLY {steps_remaining} STEPS LEFT !!!
Call finish NOW with your best candidates!
"""
        elif steps_remaining <= 5:
            deadline_warning = f"""
NOTE: {steps_remaining} steps remaining.
"""

        fetch_count = self.tools.get_fetch_count()
        fetch_warning = ""
        if fetch_count >= 3:
            fetch_warning = f"""
WARNING: you have already fetched {fetch_count} models!
Think hard about whether you really need any more.
"""

        # === CACHED MODELS INFO ===
        cached_models_info = ""
        if self.pre_fetched_models:
            cached_list = []
            for model_id in self.pre_fetched_models.keys():
                metadata = self.pre_fetched_metadata.get(model_id, {})
                title = metadata.get("title", model_id)
                classes = metadata.get("classes", [])
                classes_str = ", ".join(classes[:5]) if classes else "unknown"
                cached_list.append(f"  - {model_id}: {title} (classes: {classes_str})")

            cached_models_info = f"""
=== MODELS ALREADY AVAILABLE (FROM CACHE) ===
These models were loaded during earlier requests and are available IMMEDIATELY:
{chr(10).join(cached_list)}

IMPORTANT: if one of them fits the request, use it WITHOUT paying for another fetch!
Just call fetch_model() - the content is served from the cache (FREE).
"""

        # === SESSION CONTEXT ===
        session_context = ""

        # Previous conversation
        if self._conversation_history:
            session_context += "\n=== CONVERSATION SO FAR IN THIS SESSION ===\n"
            for msg in self._conversation_history[-6:]:  # Last 3 exchanges
                role = "User" if msg.get("role") == "user" else "Agent"
                content = msg.get("content", "")[:200]
                if len(msg.get("content", "")) > 200:
                    content += "..."
                session_context += f"{role}: {content}\n"

        # Previous catalog searches
        if self._catalog_search_history:
            session_context += "\n=== CATALOG SEARCHES ALREADY PERFORMED ===\n"
            session_context += "!!! IMPORTANT: check FIRST whether the answer is already here !!!\n"
            session_context += "If a suitable model has already turned up, go straight to fetch_model instead of searching again!\n\n"
            for entry in self._catalog_search_history:
                session_context += f"- Search '{entry.get('query', '')}': {entry.get('total_found', 0)} hits\n"
                for r in entry.get('results', [])[:5]:
                    title = r.get('title', r.get('model_name', 'Unknown'))
                    identifier = r.get('identifier', r.get('id', ''))
                    session_context += f"    - {title} (ID: {identifier})\n"

        return f"""You are a catalog-first retrieval agent inside a RAG system.
{session_context}

=== YOUR JOB ===
Find the semantic models (TTL files) that are relevant to the user's request.
{cached_models_info}

!!! EFFICIENCY RULE - THIS COMES FIRST !!!
Before you do ANYTHING else, check:
1. Are there CATALOG SEARCHES ALREADY PERFORMED above? -> Reuse those results!
2. Are there MODELS ALREADY AVAILABLE (FROM CACHE) above? -> Fetch those directly!
3. Only when neither fits the current request should you start a new search.

Example: the user previously asked about "charging stations in Wuppertal" and now asks
"compare the charging stations in Wuppertal and Rostock" -> the Wuppertal models are
already here. Search for Rostock ONLY; do not look up Wuppertal a second time.

COST DISCIPLINE:
- search_catalog is FREE - but pointless when you already have the results
- fetch_model from cache is FREE - lean on the cached models
- fetch_model without a cache hit is EXPENSIVE - only when you truly need it

{CATALOG_TOOL_DESCRIPTIONS}

=== YOUR STRATEGY ===

STEP 0 - CHECK THE CACHE (ALWAYS DO THIS FIRST):
See whether the earlier searches or the cached models already cover the request.
- If YES: use them straight away (fetch_model for cached models, or finish with the known IDs)
- If PARTLY: search only for the pieces that are missing
- If NO: carry on with step 1

STEP 1 - EXTRACT KEYWORDS:
Identify the most important terms in the user's request.
Example: "show charging stations in Wuppertal" -> keywords: "charging station", "Wuppertal", "electric mobility"

STEP 2 - TARGETED CATALOG SEARCH:
Call search_catalog() with the keywords you extracted.
IMPORTANT: pick SPECIFIC keywords, never generic ones!
- GOOD: search_catalog(query="charging station electric mobility")
- BAD:  search_catalog(query="all data")

STEP 3 - JUDGE THE METADATA (WITHOUT FETCHING!):
- Do the class names line up with the request?
- Are the relevant properties there?
- Does the description actually match?
- Is the geographic and thematic context right?

STEP 4 - FETCH SELECTIVELY:
Call fetch_model() only when the metadata is CLEARLY promising.
Fetch AT MOST 2-3 models!
After each fetch, check whether the model really fits.

STEP 5 - DECIDE:
Once you have enough relevant models, call finish().
LESS IS MORE: one or two precise models beat five vague ones.

=== FALLBACK STRATEGY ===
When search_catalog turns up NOTHING, or you have no idea what to search for:
1. Try different keywords (synonyms, related terms)
2. Still nothing? Fall back to list_catalog_datasets() or get_corpus_overview()
3. Those tools show the whole catalog - mine them for usable keywords

IMPORTANT: fetch at most 2-3 models!

=== DEADLINE ===
Maximum steps: {self.max_steps}
Current step: {current_step + 1}
Fetches so far: {fetch_count}
{deadline_warning}
{fetch_warning}

=== RESPONSE FORMAT (always JSON) ===

For tool calls:
{{
    "thought": "brief reasoning",
    "action": "tool_name",
    "action_input": {{"param": "value"}}
}}

For the final decision:
{{
    "thought": "why you picked these",
    "action": "finish",
    "action_input": {{
        "selected_models": ["model1.ttl", "model2.ttl"],
        "reasoning": "These models contain..."
    }}
}}

IMPORTANT:
- Check FIRST whether a matching search or model is already cached!
- Call search_catalog ONLY when nothing suitable is available yet!
- Study the metadata BEFORE you fetch!
- Fetch at most 2-3 models!
"""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response as JSON."""
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

        return {
            "thought": response,
            "action": "finish",
            "action_input": {"selected_models": [], "reasoning": "Parsing failed"}
        }

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Run a tool synchronously."""
        # Check for cached fetch_model call
        if tool_name == "fetch_model":
            identifier = tool_input.get("identifier", "")
            if identifier in self.pre_fetched_models:
                logger.info(f"[CatalogRetriever] Returning cached model: {identifier}")
                metadata = self.pre_fetched_metadata.get(identifier, {})
                return ToolResult(
                    success=True,
                    data={
                        "identifier": identifier,
                        "content": self.pre_fetched_models[identifier],
                        "title": metadata.get("title", identifier),
                        "data_url": metadata.get("data_url"),
                        "from_cache": True
                    },
                    message=f"Model '{identifier}' served from cache (no network fetch)"
                )

        tool_map = {
            "list_catalog_datasets": lambda: self.tools.list_catalog_datasets(),
            "search_catalog": lambda: self.tools.search_catalog(
                query=tool_input.get("query", ""),
                top_k=tool_input.get("top_k", 20),
            ),
            "get_catalog_entry": lambda: self.tools.get_catalog_entry(
                tool_input.get("identifier", "")
            ),
            "fetch_model": lambda: self.tools.fetch_model(
                tool_input.get("identifier", "")
            ),
        }

        if tool_name in tool_map:
            return tool_map[tool_name]()
        else:
            return ToolResult(
                success=False,
                data=None,
                message=f"Unknown tool: {tool_name}"
            )

    async def _execute_tool_async(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Run a tool asynchronously."""
        # Check for cached fetch_model call
        if tool_name == "fetch_model":
            identifier = tool_input.get("identifier", "")
            if identifier in self.pre_fetched_models:
                logger.info(f"[CatalogRetriever] Returning cached model (async): {identifier}")
                metadata = self.pre_fetched_metadata.get(identifier, {})
                return ToolResult(
                    success=True,
                    data={
                        "identifier": identifier,
                        "content": self.pre_fetched_models[identifier],
                        "title": metadata.get("title", identifier),
                        "data_url": metadata.get("data_url"),
                        "from_cache": True
                    },
                    message=f"Model '{identifier}' served from cache (no network fetch)"
                )

        tool_map = {
            "list_catalog_datasets": lambda: self.tools.list_catalog_datasets_async(),
            "search_catalog": lambda: self.tools.search_catalog_async(
                query=tool_input.get("query", ""),
                top_k=tool_input.get("top_k", 20),
            ),
            "get_catalog_entry": lambda: self.tools.get_catalog_entry_async(
                tool_input.get("identifier", "")
            ),
            "fetch_model": lambda: self.tools.fetch_model_async(
                tool_input.get("identifier", "")
            ),
        }

        if tool_name in tool_map:
            return await tool_map[tool_name]()
        else:
            return ToolResult(
                success=False,
                data=None,
                message=f"Unknown tool: {tool_name}"
            )

    def retrieve(self, query: str, verbose: bool = False) -> AgentResult:
        """
        Run the agent-driven retrieval loop (sync).

        Args:
            query: the user's request
            verbose: whether to log the details of each step

        Returns:
            An AgentResult holding the models that were found
        """
        result = AgentResult(query=query)

        base_user_message = f"Find the semantic models relevant to:\n\n{query}"

        for step_num in range(self.max_steps):
            if verbose:
                logger.info(f"Step {step_num + 1}/{self.max_steps}")

            system_prompt = self._build_system_prompt(current_step=step_num)

            # Build message for LLM
            full_prompt = f"{system_prompt}\n\nUser: {base_user_message}"

            # Add previous steps as context
            for prev_step in result.steps:
                prev_action = {
                    "thought": prev_step.thought,
                    "action": prev_step.tool,
                    "action_input": prev_step.tool_input
                }
                full_prompt += f"\n\nAssistant: {json.dumps(prev_action, ensure_ascii=False)}"

                if prev_step.tool_result:
                    result_data = json.dumps(
                        prev_step.tool_result.data,
                        indent=2,
                        ensure_ascii=False
                    )
                    if len(result_data) > 3000:
                        result_data = result_data[:3000] + "\n... (truncated)"

                    full_prompt += f"\n\nTool result:\n{prev_step.tool_result.message}\n\nData:\n{result_data}"

            # Call LLM
            llm_response = self.llm.invoke(full_prompt)

            if verbose:
                logger.info(f"LLM response: {llm_response[:200]}...")

            parsed = self._parse_llm_response(llm_response)
            thought = parsed.get("thought", "")
            action = parsed.get("action", "finish")
            action_input = parsed.get("action_input", {})

            if verbose:
                logger.info(f"Action: {action}, Input: {json.dumps(action_input, ensure_ascii=False)[:100]}")

            # Handle finish action
            if action == "finish":
                result.selected_models = action_input.get("selected_models", [])
                result.reasoning = action_input.get("reasoning", "")
                result.success = len(result.selected_models) > 0
                result.fetch_count = self.tools.get_fetch_count()
                result.cache_stats = self.tools.get_cache_stats()

                # Collect model contents and dataset URLs from fetched models
                for step in result.steps:
                    if step.tool == "fetch_model" and step.tool_result and step.tool_result.success:
                        model_id = step.tool_input.get("identifier", "")
                        content = step.tool_result.data.get("content", "")
                        data_url = step.tool_result.data.get("data_url")
                        title = step.tool_result.data.get("title", model_id)

                        if model_id and content:
                            result.model_contents[model_id] = content

                        # Collect the dataset URLs Comunica will execute against
                        if data_url:
                            result.dataset_urls.append(DatasetUrl(
                                url=data_url,
                                title=title,
                                identifier=model_id
                            ))

                if verbose:
                    logger.info(f"Finished at step {step_num + 1} with {len(result.selected_models)} models")
                break

            # Execute tool
            tool_result = self._execute_tool(action, action_input)

            step = AgentStep(
                thought=thought,
                tool=action,
                tool_input=action_input,
                tool_result=tool_result,
            )
            result.steps.append(step)

            if verbose:
                logger.info(f"Tool result: {tool_result.message}")

        # If no decision was made
        if not result.selected_models and result.steps:
            result.reasoning = "The agent never reached a decision"

        result.fetch_count = self.tools.get_fetch_count()
        result.cache_stats = self.tools.get_cache_stats()

        # Cleanup
        self.tools.close()

        return result

    async def retrieve_async(self, query: str, verbose: bool = False) -> AgentResult:
        """
        Run the agent-driven retrieval loop (async).

        Args:
            query: the user's request
            verbose: whether to log the details of each step

        Returns:
            An AgentResult holding the models that were found
        """
        result = AgentResult(query=query)

        # Log available context for debugging
        logger.info(f"[CatalogRetriever] Query: '{query[:80]}...'")
        logger.info(f"[CatalogRetriever] Available context: {len(self._catalog_search_history)} searches, {len(self.pre_fetched_models)} cached models")
        if self._catalog_search_history:
            for entry in self._catalog_search_history:
                logger.info(f"[CatalogRetriever]   - Prev search: '{entry.get('query', '')[:50]}' -> {entry.get('total_found', 0)} results")

        base_user_message = f"Find the semantic models relevant to:\n\n{query}"

        for step_num in range(self.max_steps):
            if verbose:
                logger.info(f"Step {step_num + 1}/{self.max_steps}")

            system_prompt = self._build_system_prompt(current_step=step_num)

            # Build message for LLM
            full_prompt = f"{system_prompt}\n\nUser: {base_user_message}"

            # Add previous steps as context
            for prev_step in result.steps:
                prev_action = {
                    "thought": prev_step.thought,
                    "action": prev_step.tool,
                    "action_input": prev_step.tool_input
                }
                full_prompt += f"\n\nAssistant: {json.dumps(prev_action, ensure_ascii=False)}"

                if prev_step.tool_result:
                    result_data = json.dumps(
                        prev_step.tool_result.data,
                        indent=2,
                        ensure_ascii=False
                    )
                    if len(result_data) > 3000:
                        result_data = result_data[:3000] + "\n... (truncated)"

                    full_prompt += f"\n\nTool result:\n{prev_step.tool_result.message}\n\nData:\n{result_data}"

            # Call LLM (run in thread pool since most LLMs are sync)
            llm_response = await asyncio.to_thread(self.llm.invoke, full_prompt)

            if verbose:
                logger.info(f"LLM response: {llm_response[:200]}...")

            parsed = self._parse_llm_response(llm_response)
            thought = parsed.get("thought", "")
            action = parsed.get("action", "finish")
            action_input = parsed.get("action_input", {})

            # Always log agent decisions for debugging efficiency
            logger.info(f"[CatalogRetriever] Step {step_num+1}: action={action}, thought={thought[:120]}...")

            # Handle finish action
            if action == "finish":
                result.selected_models = action_input.get("selected_models", [])
                result.reasoning = action_input.get("reasoning", "")
                result.success = len(result.selected_models) > 0
                result.fetch_count = self.tools.get_fetch_count()
                result.cache_stats = self.tools.get_cache_stats()

                # Collect model contents and dataset URLs from fetched models
                for step in result.steps:
                    if step.tool == "fetch_model" and step.tool_result and step.tool_result.success:
                        model_id = step.tool_input.get("identifier", "")
                        content = step.tool_result.data.get("content", "")
                        data_url = step.tool_result.data.get("data_url")
                        title = step.tool_result.data.get("title", model_id)

                        if model_id and content:
                            result.model_contents[model_id] = content

                        # Collect the dataset URLs Comunica will execute against
                        if data_url:
                            result.dataset_urls.append(DatasetUrl(
                                url=data_url,
                                title=title,
                                identifier=model_id
                            ))

                if verbose:
                    logger.info(f"Finished at step {step_num + 1} with {len(result.selected_models)} models")
                break

            # Execute tool asynchronously
            tool_result = await self._execute_tool_async(action, action_input)

            step = AgentStep(
                thought=thought,
                tool=action,
                tool_input=action_input,
                tool_result=tool_result,
            )
            result.steps.append(step)

            if verbose:
                logger.info(f"Tool result: {tool_result.message}")

        # If no decision was made
        if not result.selected_models and result.steps:
            result.reasoning = "The agent never reached a decision"

        result.fetch_count = self.tools.get_fetch_count()
        result.cache_stats = self.tools.get_cache_stats()

        # Cleanup
        await self.tools.aclose()

        return result
