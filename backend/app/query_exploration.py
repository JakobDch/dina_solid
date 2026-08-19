"""
Query exploration.

A semantic model states that a property holds a string, not which strings
occur, so a query written from the question alone often misses on the first
attempt: asking in German about "Kobalt" finds nothing in data that spells it
"Cobalt". Handing back an empty result in that situation is wrong - the data
can answer, the query just asked the wrong way.

So the agent gets a tool instead of a single attempt. It loads the datasets
once, then runs as many queries as it likes against them - looking at what
values exist, trying a filter, widening it, checking a join - and decides for
itself when the answer is good. Only that final answer reaches the
conversation.

Loading happens with the user's own access token, so the agent sees exactly
what the user is allowed to see and nothing more.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from rdflib import Graph

logger = logging.getLogger(__name__)

# Rows returned to the agent for a single exploratory query. Enough to judge
# whether a query is right, small enough to keep the prompt affordable.
EXPLORATION_ROW_LIMIT = 25

# Rows carried into the final answer.
FINAL_ROW_LIMIT = 500

# A stop that only catches a genuinely stuck loop; the agent normally finishes
# in two or three queries and says so itself.
MAX_EXPLORATION_STEPS = 40

# Content types a pod reports for files it will not classify further.
OPAQUE_MEDIA_TYPES = {"application/octet-stream", "binary/octet-stream", ""}


@dataclass
class ExplorationStep:
    """One query the agent ran while working towards an answer."""

    query: str
    row_count: int
    thought: str = ""
    error: Optional[str] = None


@dataclass
class ExplorationResult:
    """What the agent settled on, plus how it got there."""

    success: bool
    query: Optional[str] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    variables: List[str] = field(default_factory=list)
    steps: List[ExplorationStep] = field(default_factory=list)
    message: str = ""


class DatasetGraph:
    """The datasets under discussion, queryable in memory.

    Loading once and querying many times is what makes free exploration
    affordable: without it every attempt would cost a round trip to the pod and
    back through the browser.
    """

    def __init__(self, auth_token: Optional[str] = None, timeout: float = 60.0):
        self._graph = Graph()
        self._auth_token = auth_token
        self._timeout = timeout
        self._loaded: List[str] = []
        self._failed: Dict[str, str] = {}

    @property
    def triple_count(self) -> int:
        return len(self._graph)

    @property
    def loaded_urls(self) -> List[str]:
        return list(self._loaded)

    @property
    def failures(self) -> Dict[str, str]:
        return dict(self._failed)

    async def load(self, urls: List[str]) -> None:
        """Fetch and parse the given datasets, skipping any that fail.

        One unreadable dataset should not sink a question that the others can
        answer, so failures are recorded and reported rather than raised.
        """
        headers = {"Accept": "text/turtle;q=1.0, application/ld+json;q=0.8, */*;q=0.5"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            responses = await asyncio.gather(
                *(client.get(url) for url in urls), return_exceptions=True
            )

        for url, response in zip(urls, responses):
            if isinstance(response, Exception):
                self._failed[url] = str(response)
                continue
            if response.status_code >= 400:
                self._failed[url] = f"HTTP {response.status_code}"
                continue
            try:
                self._graph.parse(data=response.text, format=self._format_for(url, response))
                self._loaded.append(url)
            except Exception as exc:
                self._failed[url] = f"could not parse: {exc}"

        logger.info(
            f"[Exploration] Loaded {len(self._loaded)}/{len(urls)} datasets, "
            f"{self.triple_count} triples"
        )

    @staticmethod
    def _format_for(url: str, response: httpx.Response) -> str:
        """Pick a parser, falling back to the file extension.

        A pod serves a file with the content type it was uploaded under, so RDF
        added through a generic upload arrives as application/octet-stream.
        """
        declared = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
        by_media_type = {
            "text/turtle": "turtle",
            "application/trig": "trig",
            "application/n-triples": "nt",
            "application/n-quads": "nquads",
            "application/ld+json": "json-ld",
            "application/rdf+xml": "xml",
        }
        if declared in by_media_type:
            return by_media_type[declared]

        by_extension = [
            (".ttl", "turtle"), (".trig", "trig"), (".nt", "nt"),
            (".nq", "nquads"), (".jsonld", "json-ld"), (".json", "json-ld"),
            (".rdf", "xml"), (".xml", "xml"),
        ]
        lowered = url.lower()
        for suffix, fmt in by_extension:
            if lowered.endswith(suffix):
                return fmt
        return "turtle"

    def run(self, sparql_query: str, limit: int) -> Dict[str, Any]:
        """Run a query and return rows in the shape the frontend already uses."""
        result = self._graph.query(sparql_query)

        variables = [str(v) for v in (result.vars or [])]
        rows: List[Dict[str, Any]] = []
        for binding in result:
            row: Dict[str, Any] = {}
            for name in variables:
                term = binding.get(name) if hasattr(binding, "get") else None
                if term is not None:
                    row[name] = {
                        "value": str(term),
                        "type": "uri" if hasattr(term, "n3") and str(term).startswith("http") else "literal",
                    }
            rows.append(row)
            if len(rows) >= limit:
                break

        return {"rows": rows, "variables": variables, "total": len(rows)}


EXPLORATION_PROMPT = """You are querying a set of RDF datasets to answer a question.

QUESTION
{user_query}

SEMANTIC MODEL OF THE DATA
{model_content}

DATA LOADED
{dataset_summary}

WHAT YOU HAVE DONE SO FAR
{history}

You can run as many SPARQL queries as you need. Use that: look at which values
a property actually holds before filtering on it, try a pattern, widen it if it
returns nothing, check a join. The model tells you the shape of the data, not
its contents - a filter guessed from the question's wording often misses, and
the values may be in a different language than the question.

Answer with JSON and nothing else:

{{"thought": "what you make of the last result and what you want to try next",
 "action": "query" or "answer",
 "sparql": "the query to run, when action is query",
 "summary": "what the final result shows, when action is answer"}}

Use action "answer" once a query returns what the question asked for. Use it
also when you are convinced the data cannot answer - say so in the summary
rather than returning something unrelated.
"""


def parse_agent_json(text: str) -> Optional[dict]:
    """Read the JSON object out of a model response."""
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def format_history(steps: List[ExplorationStep]) -> str:
    """Describe the queries run so far, so the agent can build on them."""
    if not steps:
        return "Nothing yet - this is your first query."

    lines = []
    for index, step in enumerate(steps, start=1):
        outcome = step.error if step.error else f"{step.row_count} rows"
        lines.append(f"{index}. {step.query.strip()}\n   -> {outcome}")
    return "\n".join(lines)


def summarise_rows(rows: List[Dict[str, Any]], variables: List[str]) -> str:
    """Render a few rows compactly for the prompt."""
    if not rows:
        return "(no rows)"

    lines = []
    for row in rows[:8]:
        cells = [f"{name}={row.get(name, {}).get('value', '')}" for name in variables]
        lines.append("  " + ", ".join(cells))
    if len(rows) > 8:
        lines.append(f"  ... and {len(rows) - 8} more")
    return "\n".join(lines)


async def explore(
    user_query: str,
    dataset_urls: List[str],
    model_content: str,
    llm,
    auth_token: Optional[str] = None,
    on_step=None,
) -> ExplorationResult:
    """Let the agent query the data until it is satisfied with the answer.

    Args:
        user_query: the question, in the user's own words
        dataset_urls: datasets the retrieval step selected
        model_content: their semantic model, describing the shape of the data
        llm: the language model deciding what to try next
        auth_token: the user's Solid token, so protected pods can be read
        on_step: optional async callback, invoked per query for progress
            reporting. Exploration is background work, so these belong in the
            reasoning trace rather than the conversation.

    Returns:
        What the agent settled on, along with the queries it ran to get there.
    """
    graph = DatasetGraph(auth_token=auth_token)
    await graph.load(dataset_urls)

    if graph.triple_count == 0:
        detail = "; ".join(f"{url}: {reason}" for url, reason in graph.failures.items())
        return ExplorationResult(
            success=False,
            message=f"None of the selected datasets could be read. {detail}",
        )

    dataset_summary = (
        f"{len(graph.loaded_urls)} dataset(s), {graph.triple_count} triples.\n"
        + "\n".join(f"- {url}" for url in graph.loaded_urls)
    )
    if graph.failures:
        dataset_summary += "\nUnreadable: " + ", ".join(graph.failures)

    steps: List[ExplorationStep] = []
    last_rows: List[Dict[str, Any]] = []
    last_variables: List[str] = []
    last_query: Optional[str] = None
    observation = ""

    for _ in range(MAX_EXPLORATION_STEPS):
        prompt = EXPLORATION_PROMPT.format(
            user_query=user_query,
            model_content=(model_content or "(no model available)")[:6000],
            dataset_summary=dataset_summary,
            history=format_history(steps) + (f"\n\nLast result:\n{observation}" if observation else ""),
        )

        try:
            raw = await asyncio.to_thread(llm.invoke, prompt)
        except Exception as exc:
            logger.warning(f"[Exploration] Model call failed: {exc}")
            break

        decision = parse_agent_json(raw)
        if not decision:
            logger.warning("[Exploration] Could not read the model's decision, stopping")
            break

        thought = str(decision.get("thought", ""))[:400]

        if decision.get("action") == "answer":
            return ExplorationResult(
                success=bool(last_rows),
                query=last_query,
                rows=last_rows,
                variables=last_variables,
                steps=steps,
                message=str(decision.get("summary", "")),
            )

        sparql = decision.get("sparql")
        if not sparql:
            break

        if on_step:
            await on_step(len(steps) + 1, thought)

        try:
            outcome = graph.run(sparql, limit=FINAL_ROW_LIMIT)
            rows, variables = outcome["rows"], outcome["variables"]
            steps.append(ExplorationStep(query=sparql, row_count=len(rows), thought=thought))

            # Keep the last query that actually produced something, so a final
            # "answer" after an exploratory dead end still returns real rows.
            if rows:
                last_rows, last_variables, last_query = rows, variables, sparql

            observation = summarise_rows(rows[:EXPLORATION_ROW_LIMIT], variables)
            logger.info(f"[Exploration] Step {len(steps)}: {len(rows)} rows")
        except Exception as exc:
            steps.append(ExplorationStep(query=sparql, row_count=0, thought=thought, error=str(exc)))
            observation = f"The query failed: {exc}"
            logger.info(f"[Exploration] Step {len(steps)} failed: {exc}")

    # Ran out of steps or the model stopped deciding: report the best we saw.
    return ExplorationResult(
        success=bool(last_rows),
        query=last_query,
        rows=last_rows,
        variables=last_variables,
        steps=steps,
        message="" if last_rows else "No query returned matching data.",
    )
