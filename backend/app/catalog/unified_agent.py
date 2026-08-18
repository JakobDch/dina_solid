"""
Unified Catalog Agent - one agent for every kind of request.

It picks its own tools:
- search the catalog (search_catalog, get_corpus_overview)
- retrieve models (fetch_model)
- generate and run SPARQL
- chart the results (create_visualization)
- crunch the numbers (perform_calculation)
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .tools import CatalogTools, ToolResult, CATALOG_TOOL_DESCRIPTIONS

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """One step of the agent's execution plan."""
    step_number: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    result: Optional[ToolResult] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class UnifiedAgentResult:
    """The outcome of an agent run."""
    success: bool
    message: str
    steps: List[AgentStep] = field(default_factory=list)
    final_data: Optional[Dict[str, Any]] = None
    sparql_results: Optional[List[Dict]] = None
    visualization: Optional[Dict[str, Any]] = None
    calculation: Optional[Dict[str, Any]] = None
    selected_models: List[str] = field(default_factory=list)


class UnifiedCatalogAgent:
    """
    A single agent covering every catalog operation.

    What it can do:
    - search the catalog
    - list datasets (this replaces CORPUS_INFO)
    - generate and run SPARQL
    - chart the results
    - crunch the numbers
    """

    def __init__(
        self,
        llm,
        graphdb_url: str = "",
        workspace_id: str = "",
        auth_token: Optional[str] = None,
        max_steps: int = 20,
        catalog_api_url: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        catalog_search_history: Optional[List[Dict]] = None,
        pre_loaded_catalog_entries: Optional[List] = None,
    ):
        """
        Initialise the UnifiedCatalogAgent.

        Args:
            llm: the LLM instance (DeepSeekLLM, OpenAILLM, ...)
            graphdb_url: URL of the GraphDB instance
            workspace_id: workspace ID used with GraphDB
            auth_token: optional Solid auth token
            max_steps: how many steps the agent may take
            catalog_api_url: optional catalog URL
            conversation_history: what has been said so far in this session
            catalog_search_history: catalog searches already performed
            pre_loaded_catalog_entries: catalog entries cached by the session
        """
        self.llm = llm
        self.graphdb_url = graphdb_url
        self.workspace_id = workspace_id
        self.max_steps = max_steps
        self.tools = CatalogTools(
            catalog_api_url=catalog_api_url,
            auth_token=auth_token,
            pre_loaded_catalog_entries=pre_loaded_catalog_entries,
        )

        # State carried through a single run
        self._current_results: Optional[List[Dict]] = None
        self._selected_models: List[str] = []
        self._model_contents: Dict[str, str] = {}

        # Context inherited from the session
        self._conversation_history = conversation_history or []
        self._catalog_search_history = catalog_search_history or []

    def get_catalog_entries(self) -> List:
        """Return the loaded catalog entries so the session can cache them."""
        return self.tools.get_catalog_entries()

    async def execute_async(
        self,
        user_query: str,
        emit_event: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """
        The main run loop, streaming SSE events.
        The agent reads the request and decides which tools it needs.

        Args:
            user_query: the user's request
            emit_event: optional callback for SSE events

        Yields:
            SSE event strings
        """
        from ..utils import format_sse_event

        steps: List[AgentStep] = []

        # 1. Look at the request
        yield await format_sse_event({
            "message": "Analysing request...",
            "step_id": "analyze",
            "query": user_query
        }, "pipeline_update")

        # 2. Enter the agent loop
        for step_num in range(self.max_steps):
            # Build the system prompt, including everything done so far
            system_prompt = self._build_system_prompt(user_query, steps)

            # Ask the LLM what to do next
            try:
                response = await self._call_llm(system_prompt)
                thought, action, action_input = self._parse_response(response)
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                yield await format_sse_event({
                    "message": f"LLM error: {str(e)}",
                    "step_id": f"error_{step_num}",
                    "is_error": True
                }, "pipeline_error")
                break

            # Stream a status update
            yield await format_sse_event({
                "message": f"Step {step_num + 1}: {action}",
                "thought": thought,
                "step_id": f"step_{step_num}"
            }, "pipeline_update")

            # Handle the finish action
            if action == "finish":
                # Emit the final answer
                yield await format_sse_event({
                    "message": thought or "Request handled",
                    "selected_models": self._selected_models,
                    "step_id": "finish"
                }, "agent_response")
                break

            # Run the tool
            result = await self._execute_tool_async(action, action_input)

            step = AgentStep(
                step_number=step_num + 1,
                thought=thought,
                action=action,
                action_input=action_input,
                result=result
            )
            steps.append(step)

            # Stream the events specific to this tool
            if action == "create_visualization" and result.success:
                yield await format_sse_event({
                    "image": result.data.get("image"),
                    "chart_type": result.data.get("chart_type"),
                    "data_points": result.data.get("data_points"),
                    "step_id": f"viz_{step_num}"
                }, "visualization_result")

            elif action == "perform_calculation" and result.success:
                yield await format_sse_event({
                    "operation": result.data.get("operation"),
                    "column": result.data.get("column"),
                    "result": result.data.get("result"),
                    "step_id": f"calc_{step_num}"
                }, "calculation_result")

            elif action == "get_corpus_overview" and result.success:
                yield await format_sse_event({
                    "total_datasets": result.data.get("total_datasets"),
                    "themes": result.data.get("themes"),
                    "datasets_preview": result.data.get("datasets", [])[:10],
                    "step_id": f"corpus_{step_num}"
                }, "corpus_info")

            elif action == "search_catalog" and result.success:
                yield await format_sse_event({
                    "total_found": result.data.get("total_found"),
                    "results": result.data.get("results", [])[:5],
                    "step_id": f"search_{step_num}"
                }, "search_results")

            elif action == "fetch_model" and result.success:
                model_id = action_input.get("identifier", "")
                self._selected_models.append(model_id)
                self._model_contents[model_id] = result.data.get("content", "")
                yield await format_sse_event({
                    "model_name": result.data.get("model_name"),
                    "fetch_number": result.data.get("fetch_number"),
                    "source": result.data.get("source"),
                    "step_id": f"fetch_{step_num}"
                }, "model_fetched")

            # Surface any tool failure
            if not result.success:
                yield await format_sse_event({
                    "message": result.message,
                    "action": action,
                    "step_id": f"tool_error_{step_num}",
                    "is_error": True
                }, "tool_error")

        # 3. Closing event
        yield await format_sse_event({
            "message": "Agent pipeline finished",
            "total_steps": len(steps),
            "models_selected": self._selected_models,
            "step_id": "agent_ended"
        }, "end_stream")

    def _build_system_prompt(self, user_query: str, steps: List[AgentStep]) -> str:
        """Build the system prompt from the tool descriptions and the steps taken so far."""

        # Recap of the steps taken so far
        steps_text = ""
        if steps:
            steps_text = "\n\nSTEPS SO FAR:\n"
            for step in steps:
                result_summary = ""
                if step.result:
                    if step.result.success:
                        result_summary = f"Succeeded: {step.result.message}"
                    else:
                        result_summary = f"Failed: {step.result.message}"
                steps_text += f"\nStep {step.step_number}:\n"
                steps_text += f"  Thought: {step.thought}\n"
                steps_text += f"  Action: {step.action}\n"
                steps_text += f"  Input: {json.dumps(step.action_input, ensure_ascii=False)}\n"
                steps_text += f"  Result: {result_summary}\n"

        # What has already been said in this session
        conv_context = ""
        if self._conversation_history:
            conv_context = "\n\nCONVERSATION SO FAR IN THIS SESSION:\n"
            for msg in self._conversation_history[-6:]:  # last 3 exchanges
                role = "User" if msg.get("role") == "user" else "Agent"
                content = msg.get("content", "")[:200]
                if len(msg.get("content", "")) > 200:
                    content += "..."
                conv_context += f"{role}: {content}\n"

        # Catalog searches that already ran
        search_context = ""
        if self._catalog_search_history:
            search_context = "\n\nCATALOG SEARCHES ALREADY PERFORMED (reuse these results!):\n"
            for entry in self._catalog_search_history:
                search_context += f"- Search '{entry.get('query', '')}': {entry.get('total_found', 0)} hits\n"
                for r in entry.get('results', [])[:5]:
                    title = r.get('title', r.get('model_name', 'Unknown'))
                    search_context += f"  - {title}\n"

        # Results currently on hand
        results_context = ""
        if self._current_results:
            results_context = f"\n\nAVAILABLE RESULTS:\n{len(self._current_results)} rows from an earlier SPARQL query"
            if self._current_results:
                sample = self._current_results[:3]
                results_context += f"\nSample: {json.dumps(sample, ensure_ascii=False, indent=2)}"

        return f"""You are a data agent for ESG reporting.
You work against a remote data catalog (Solid Pods) and help users find the data they need.

{CATALOG_TOOL_DESCRIPTIONS}

YOUR JOB:
Answer the user's request: "{user_query}"

STRATEGY:
1. Asked what data exists -> get_corpus_overview()
2. Looking for data -> search_catalog() -> (if needed) get_catalog_entry() -> fetch_model()
3. Asked for a chart -> create_visualization() (only once results exist)
4. Asked for a calculation -> perform_calculation() (only once results exist)
5. Done -> finish()
{conv_context}
{search_context}
{steps_text}
{results_context}

IMPORTANT:
- REUSE THE SEARCH RESULTS YOU ALREADY HAVE! If catalog searches are listed above, work from them instead of searching again.
- Reach for the FREE tools (search_catalog, get_corpus_overview) first!
- fetch_model is EXPENSIVE - use it only when you must!
- ALWAYS answer in this JSON format:

{{"thought": "your reasoning", "action": "tool_name", "action_input": {{"param": "value"}}}}

An example of finishing:
{{"thought": "I found the available data and can answer the question.", "action": "finish", "action_input": {{"summary": "a short summary"}}}}
"""

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM and return its response as text."""
        try:
            # Prefer async invocation where the LLM supports it
            if hasattr(self.llm, 'ainvoke'):
                response = await self.llm.ainvoke(prompt)
            else:
                # Otherwise run the sync call in a thread
                response = await asyncio.to_thread(self.llm.invoke, prompt)

            # The response may be a plain string or an AIMessage
            if hasattr(response, 'content'):
                return response.content
            return str(response)
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            raise

    def _parse_response(self, response: str) -> tuple:
        """Parse the LLM response into thought, action and action_input."""
        try:
            # Try to parse the JSON; models often wrap it in a markdown fence
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)
            thought = data.get("thought", "")
            action = data.get("action", "finish")
            action_input = data.get("action_input", {})

            return thought, action, action_input

        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse LLM response as JSON: {e}")
            # Fallback: salvage what we can from the raw text
            return response[:200], "finish", {"summary": "Parsing error"}

    async def _execute_tool_async(self, action: str, action_input: Dict[str, Any]) -> ToolResult:
        """Run a tool asynchronously."""
        try:
            if action == "search_catalog":
                return await self.tools.search_catalog_async(
                    query=action_input.get("query", ""),
                    top_k=action_input.get("top_k", 20)
                )

            elif action == "get_catalog_entry":
                return await self.tools.get_catalog_entry_async(
                    identifier=action_input.get("identifier", "")
                )

            elif action == "list_catalog_datasets":
                return await self.tools.list_catalog_datasets_async()

            elif action == "get_corpus_overview":
                return await self.tools.get_corpus_overview_async()

            elif action == "fetch_model":
                return await self.tools.fetch_model_async(
                    identifier=action_input.get("identifier", "")
                )

            elif action == "create_visualization":
                results = action_input.get("results", self._current_results or [])
                return await self.tools.create_visualization_async(
                    results=results,
                    chart_type=action_input.get("chart_type", "bar"),
                    x_column=action_input.get("x_column", ""),
                    y_column=action_input.get("y_column", ""),
                    title=action_input.get("title", "")
                )

            elif action == "perform_calculation":
                results = action_input.get("results", self._current_results or [])
                return await self.tools.perform_calculation_async(
                    results=results,
                    operation=action_input.get("operation", "sum"),
                    column=action_input.get("column", "")
                )

            elif action == "finish":
                return ToolResult(
                    success=True,
                    data={"summary": action_input.get("summary", "Done")},
                    message="Agent run complete"
                )

            else:
                return ToolResult(
                    success=False,
                    data=None,
                    message=f"Unknown action: {action}"
                )

        except Exception as e:
            logger.error(f"Tool execution error for {action}: {e}")
            return ToolResult(
                success=False,
                data=None,
                message=f"Tool error: {str(e)}"
            )

    def set_results(self, results: List[Dict]) -> None:
        """Set the current result rows used for charting and calculation."""
        self._current_results = results

    def get_selected_models(self) -> List[str]:
        """Return the models the agent selected."""
        return self._selected_models

    def get_model_contents(self) -> Dict[str, str]:
        """Return the model contents that were loaded."""
        return self._model_contents

    async def close(self):
        """Release the underlying resources."""
        await self.tools.aclose()
