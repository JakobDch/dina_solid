"""
SPARQL Operator Predictor for Adaptive Few-Shot Prompting.

Predicts required SPARQL operators based on user query and semantic models,
then retrieves matching examples from the corpus.
"""

import json
import re
import asyncio
import logging
from typing import List, Union, Dict, Any, Optional

from .llm_services import OllamaLLM, OpenAILLM, DeepSeekLLM
from .sparql_corpus import (
    get_corpus_entries_by_operators,
    format_examples_for_prompt,
    get_all_operators
)

logger = logging.getLogger(__name__)


# --- Operator Prediction Prompt ---

OPERATOR_PREDICTION_PROMPT = """You are an expert in SPARQL query generation. Your task is to predict the required SPARQL operators based on a natural language user query and the available semantic models.

WHAT ARE SEMANTIC MODELS?
Semantic models describe the structure of RDF data. They show:
- Classes (e.g., "local:Product", "local:Company")
- Properties (connections between classes and values)
- Datatypes of properties (xsd:string, xsd:integer, xsd:decimal, xsd:date, etc.)

IMPORTANT: Analyze the datatypes of properties in the model:
- xsd:integer, xsd:decimal, xsd:float → Numeric values → Enable: SUM, AVG, COUNT, MIN, MAX, numeric FILTER
- xsd:string → Text values → Enable: CONTAINS, LCASE, UCASE, REGEX, string FILTER
- xsd:date, xsd:dateTime → Date values → Enable: temporal FILTER, ORDER BY
- Class connections → Enable: GROUP BY for grouping entities

MULTIPLE SEMANTIC MODELS:
When you are given MULTIPLE separate models:
→ Check if the query wants to combine data from BOTH models (signal words: "and", "together", "combined", "all X and Y")
→ If yes, UNION is often needed to combine results from different models
→ If the models are connected via properties, a normal JOIN without UNION may suffice

AVAILABLE SPARQL OPERATORS:
{available_operators}

KEYWORD ANALYSIS EXAMPLES:

German keywords → Operators:
- "Anzahl", "wie viele", "zähle" → COUNT
- "Durchschnitt", "durchschnittlich" → AVG
- "Summe", "gesamt", "insgesamt" → SUM
- "enthält", "beinhaltet", "mit Namen" → CONTAINS, FILTER
- "sortiert", "geordnet", "Reihenfolge" → ORDER BY
- "mehr als", "mindestens", "größer als", ">=" → FILTER with comparison
- "weniger als", "höchstens", "kleiner als" → FILTER with comparison
- "alle...und alle" → UNION (when combining different entity types)
- "pro", "je", "gruppiert nach" → GROUP BY

English keywords → Operators:
- "count", "how many", "number of" → COUNT
- "average", "mean" → AVG
- "sum", "total" → SUM
- "contains", "includes", "with name" → CONTAINS, FILTER
- "sorted", "ordered", "alphabetically" → ORDER BY
- "greater than", "more than", "at least" → FILTER
- "less than", "at most" → FILTER
- "all...and all" → UNION
- "per", "by", "grouped by" → GROUP BY

NOW YOUR TASK:

USER QUERY:
"{user_query}"

AVAILABLE SEMANTIC MODELS:
{model_info_blocks}

Answer exclusively with a JSON object in the following format:
{{
  "predicted_operators": ["OPERATOR1", "OPERATOR2", "OPERATOR3", ...],
  "reasoning": "Brief explanation: which query signals and model properties led to these operators?"
}}

Select 3-8 of the most likely operators.
"""


async def predict_sparql_operators(
    user_query: str,
    model_info_blocks: str,
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    request_id: str = "operator_prediction"
) -> Dict[str, Any]:
    """
    Predict required SPARQL operators based on user query and semantic models.

    Args:
        user_query: The natural language query from the user
        model_info_blocks: Formatted string containing semantic model content
        llm_instance: LLM instance to use for prediction
        request_id: Request ID for logging

    Returns:
        Dictionary with 'operators' list and prediction metadata
    """
    log_prefix = f"[{request_id}]"
    logger.info(f"{log_prefix} Starting SPARQL operator prediction for query: '{user_query[:100]}...'")

    # Build the prompt
    available_operators = get_all_operators()

    prompt = OPERATOR_PREDICTION_PROMPT.format(
        available_operators=', '.join(available_operators),
        user_query=user_query,
        model_info_blocks=model_info_blocks
    )

    try:
        # LLM call
        logger.debug(f"{log_prefix} Sending prediction prompt to LLM")
        llm_response = await asyncio.to_thread(llm_instance.invoke, prompt)
        # Response can be a string directly or an object with .content
        raw_response = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
        logger.debug(f"{log_prefix} Raw LLM response: {raw_response[:200]}...")

        # Parse JSON response
        json_match = re.search(r'\{[\s\S]*\}', raw_response.strip())
        if not json_match:
            logger.error(f"{log_prefix} No JSON found in LLM response: {raw_response}")
            return _fallback_operator_prediction(user_query)

        try:
            parsed_response = json.loads(json_match.group(0))
            predicted_operators = parsed_response.get("predicted_operators", [])
            reasoning = parsed_response.get("reasoning", "No reasoning provided")

            # Validate predicted operators
            if not isinstance(predicted_operators, list):
                logger.warning(f"{log_prefix} Predicted operators is not a list: {predicted_operators}")
                return _fallback_operator_prediction(user_query)

            # Filter to valid operators only
            valid_operators = [op for op in predicted_operators if op in available_operators]
            if len(valid_operators) != len(predicted_operators):
                logger.warning(f"{log_prefix} Some predicted operators were invalid. Filtered: {valid_operators}")

            if not valid_operators:
                logger.warning(f"{log_prefix} No valid operators predicted, using fallback")
                return _fallback_operator_prediction(user_query)

            logger.info(f"{log_prefix} Successfully predicted {len(valid_operators)} operators: {valid_operators}")
            logger.info(f"{log_prefix} LLM reasoning: {reasoning}")

            return {
                "operators": valid_operators,
                "reasoning": reasoning,
                "method": "llm_prediction"
            }

        except json.JSONDecodeError as e:
            logger.error(f"{log_prefix} JSON parsing failed: {e}. Raw response: {json_match.group(0)}")
            return _fallback_operator_prediction(user_query)

    except Exception as e:
        logger.error(f"{log_prefix} Error during operator prediction: {e}", exc_info=True)
        return _fallback_operator_prediction(user_query)


def _fallback_operator_prediction(user_query: str) -> Dict[str, Any]:
    """
    Fallback operator prediction using simple heuristics (no LLM call).

    Uses keyword matching for German and English queries.
    """
    query_lower = user_query.lower()
    fallback_operators = ["SELECT", "WHERE"]

    # Basic operators
    if any(word in query_lower for word in ["alle", "list", "zeige", "gib", "all", "show", "list"]):
        fallback_operators.append("DISTINCT")

    # String matching
    if any(word in query_lower for word in ["enthalten", "beinhalten", "mit", "name", "contains", "includes", "with"]):
        fallback_operators.extend(["FILTER", "CONTAINS"])

    # Counting
    if any(word in query_lower for word in ["anzahl", "wie viele", "count", "how many", "zähle"]):
        fallback_operators.append("COUNT")

    # Numeric comparisons
    if any(word in query_lower for word in ["mehr als", "mindestens", "größer", "more than", "greater", "at least", ">", ">="]):
        fallback_operators.extend(["FILTER", "xsd:integer"])

    if any(word in query_lower for word in ["weniger als", "höchstens", "kleiner", "less than", "at most", "<", "<="]):
        fallback_operators.extend(["FILTER", "xsd:integer"])

    # Aggregation
    if any(word in query_lower for word in ["durchschnitt", "average", "mean"]):
        fallback_operators.extend(["AVG", "GROUP BY"])

    if any(word in query_lower for word in ["summe", "gesamt", "sum", "total"]):
        fallback_operators.extend(["SUM", "GROUP BY"])

    # Sorting
    if any(word in query_lower for word in ["sortiert", "reihenfolge", "geordnet", "sorted", "ordered", "alphabetically"]):
        fallback_operators.append("ORDER BY")

    # Grouping
    if any(word in query_lower for word in ["pro", "je", "gruppiert", "per", "by", "grouped"]):
        fallback_operators.append("GROUP BY")

    # Union (combining different types)
    if any(word in query_lower for word in ["und", "sowie", "zusammen", "and", "together", "combined"]):
        # Only add UNION if it seems like combining different entity types
        if "alle" in query_lower or "all" in query_lower:
            fallback_operators.append("UNION")

    # Remove duplicates and return
    unique_operators = list(dict.fromkeys(fallback_operators))
    logger.info(f"Using fallback operator prediction: {unique_operators}")

    return {
        "operators": unique_operators,
        "reasoning": "Fallback heuristic prediction based on keyword matching",
        "method": "fallback_heuristic"
    }


async def get_adaptive_few_shot_examples(
    user_query: str,
    model_info_blocks: str,
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    request_id: str = "adaptive_few_shot",
    max_examples: int = 2
) -> Dict[str, Any]:
    """
    Generate adaptive few-shot examples based on predicted SPARQL operators.

    This is the main entry point for adaptive few-shot prompting.

    Args:
        user_query: The user's natural language query
        model_info_blocks: Formatted semantic model content
        llm_instance: LLM instance for operator prediction
        request_id: Request ID for logging
        max_examples: Maximum number of examples to return

    Returns:
        Dictionary with:
        - formatted_examples: String ready for prompt injection
        - examples_metadata: List of metadata about selected examples
        - predicted_operators: List of predicted operators
        - prediction_method: 'llm_prediction' or 'fallback_heuristic'
    """
    log_prefix = f"[{request_id}]"
    logger.info(f"{log_prefix} Starting adaptive few-shot example generation")

    # Step 1: Predict required operators
    prediction_result = await predict_sparql_operators(
        user_query, model_info_blocks, llm_instance, f"{request_id}_predict"
    )

    predicted_operators = prediction_result.get("operators", [])
    prediction_method = prediction_result.get("method", "unknown")

    if not predicted_operators:
        logger.warning(f"{log_prefix} No operators predicted, returning empty examples")
        return {
            "formatted_examples": "",
            "examples_metadata": [],
            "predicted_operators": [],
            "prediction_method": prediction_method
        }

    # Step 2: Find examples based on operator matching
    logger.info(f"{log_prefix} Searching for {max_examples} examples based on predicted operators: {predicted_operators}")
    matching_entries = get_corpus_entries_by_operators(
        predicted_operators,
        max_results=max_examples
    )

    if not matching_entries:
        logger.warning(
            f"{log_prefix} No matching examples found "
            f"(operators: {predicted_operators}, query: '{user_query[:50]}...')"
        )
        return {
            "formatted_examples": "",
            "examples_metadata": [],
            "predicted_operators": predicted_operators,
            "prediction_method": prediction_method
        }

    # Step 3: Format examples for the prompt
    formatted_examples = format_examples_for_prompt(matching_entries)

    # Log summary of used examples
    entry_ids = [entry.get('entry_id', 'unknown') for entry in matching_entries]
    logger.info(
        f"{log_prefix} Generated adaptive few-shot examples: "
        f"{len(matching_entries)} examples | IDs: {entry_ids}"
    )

    # Collect metadata for logging/debugging
    examples_metadata = []
    for i, entry in enumerate(matching_entries, 1):
        user_query_example = entry.get('user_query', entry.get('natural_language_query', 'N/A'))
        relevance_score = entry.get('relevance_score', 0.0)
        matching_ops = entry.get('matching_operators', [])
        example_id = entry.get('entry_id', 'unknown')
        source = entry.get('source', 'unknown')

        logger.info(
            f"{log_prefix}   [{i}] ID: {example_id} | "
            f"Score: {relevance_score:.3f} | "
            f"Source: {source} | "
            f"Matching ops: {matching_ops} | "
            f"Query: \"{user_query_example[:80]}...\""
        )

        examples_metadata.append({
            "example_entry_id": example_id,
            "example_user_query": user_query_example,
            "relevance_score": relevance_score,
            "matching_operators": matching_ops,
            "source": source
        })

    return {
        "formatted_examples": formatted_examples,
        "examples_metadata": examples_metadata,
        "predicted_operators": predicted_operators,
        "prediction_method": prediction_method
    }


def get_static_fallback_examples() -> str:
    """
    Get static fallback examples when corpus is empty or adaptive selection fails.

    Returns a hardcoded set of examples for basic SPARQL generation.
    """
    return """Here are some examples of how to solve the task:

--- Example 1 ---
User query: "Zeige mir alle Produkte mit einem Preis über 100 Euro"
Semantic models:

Model: product_model.ttl
```
local:Product local:hasName xsd:string .
local:Product local:hasPrice xsd:decimal .
local:Product local:hasCategory local:Category .
```

Hints from model check: The model contains Product with price property.
Answer:
PREFIX local: <http://dina.2mw.2ia-2.2a2-2.2a.2.2a>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT DISTINCT ?product ?name ?price
WHERE {
    ?product a local:Product ;
             local:hasName ?name ;
             local:hasPrice ?price .
    FILTER(xsd:decimal(?price) > 100)
}
--- End Example 1 ---

--- Example 2 ---
User query: "Wie viele Mitarbeiter gibt es pro Abteilung?"
Semantic models:

Model: employee_model.ttl
```
local:Employee local:hasName xsd:string .
local:Employee local:worksIn local:Department .
local:Department local:deptName xsd:string .
```

Hints from model check: The model shows Employee connected to Department.
Answer:
PREFIX local: <http://dina.2mw.2ia-2.2a2-2.2a.2.2a>

SELECT ?department ?deptName (COUNT(?employee) AS ?employeeCount)
WHERE {
    ?employee a local:Employee ;
              local:worksIn ?department .
    ?department a local:Department ;
                local:deptName ?deptName .
}
GROUP BY ?department ?deptName
ORDER BY DESC(?employeeCount)
--- End Example 2 ---
"""
