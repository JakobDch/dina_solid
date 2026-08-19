"""
SPARQL Query Generation Module

This module handles the generation and manipulation of SPARQL queries.
Extracted from query_pipeline.py for better separation of concerns.
"""

import re
import logging
import asyncio
from typing import Union, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate

from .llm_services import OllamaLLM, OpenAILLM, DeepSeekLLM
from .prompts import (
    SPARQL_GENERATOR_PROMPT_MULTI_MODEL,
    OUTPUT_INSTRUCTIONS_GENERATE_SPARQL,
    SPARQL_SYNTAX_ERROR_CORRECTION_PROMPT,
    OUTPUT_INSTRUCTIONS_SYNTAX_CORRECTION,
    SPARQL_AGENTIC_REASONER_PROMPT,
    INTERNAL_REASONING_BLOCK_WITH_SEPARATOR,
    FEW_SHOT_EXAMPLES,
    OUTPUT_SEPARATOR
)
from .operator_predictor import get_adaptive_few_shot_examples, get_static_fallback_examples

logger = logging.getLogger(__name__)

# SPARQL prefixes that should be used consistently
CORRECT_SPARQL_PREFIXES = """
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX plasma: <http://plasma.uni-wuppertal.de/ontology#>
PREFIX plcm:   <http://plasma.uni-wuppertal.de/cm#>
PREFIX plsm:   <http://plasma.uni-wuppertal.de/sm/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX local:  <https://local.ontology#>
PREFIX schema: <https://schema.org/>
PREFIX ns1:    <http://example.org/joghurt#>
PREFIX hdpe:   <http://example.org/hdpe-pipe-ontology#>
"""


def add_correct_prefixes(query_string: str, model_content: str = "") -> str:
    """Normalise the PREFIX block of a generated query.

    The well-known prefixes are always declared, because a model may rely on one
    without naming it. Prefixes the query or the model declare are kept as well:
    datasets bring their own vocabularies, and discarding those declarations
    left every query against them unresolvable. Where a name is defined twice,
    the query's own binding wins - it is what its triple patterns were written
    against.

    Args:
        query_string: the generated query
        model_content: the semantic model, so prefixes it declares survive even
            when the query omitted them

    Returns:
        The query with a complete prefix block.
    """
    if not query_string:
        return ""

    # Remove problematic Unicode characters that can interfere with SPARQL parsing
    query_string = query_string.replace('\u200B', '')  # Zero-width space
    query_string = query_string.replace('\u009f', '')  # Application Program Command (control character)
    query_string = query_string.replace('\u0080', '')  # Padding Character (control character)
    query_string = query_string.replace('\u0081', '')  # High Octet Preset (control character)

    # Remove any other control characters in the range 0x80-0x9F (Latin-1 Supplement control characters)
    import unicodedata
    query_string = ''.join(char for char in query_string if unicodedata.category(char) != 'Cc' or char in '\t\n\r')

    declaration = re.compile(r"PREFIX\s+([\w\-]*):\s*<([^>]*)>", flags=re.IGNORECASE)

    # Start from the well-known prefixes, then let the model and finally the
    # query itself override, so a dataset's own vocabulary stays resolvable.
    prefixes = dict(declaration.findall(CORRECT_SPARQL_PREFIXES))
    if model_content:
        prefixes.update(re.findall(r"@prefix\s+([\w\-]*):\s*<([^>]*)>", model_content))
    prefixes.update(declaration.findall(query_string))

    prefix_pattern = re.compile(r"^(\s*PREFIX\s+[\w\-]*:\s*<[^>]*>\s*)+", flags=re.IGNORECASE)
    query_body = prefix_pattern.sub("", query_string.strip()).strip()

    block = "\n".join(f"PREFIX {name}: <{uri}>" for name, uri in sorted(prefixes.items()))
    return f"{block}\n\n{query_body}"


def robust_sparql_sanitize(sparql_candidate: str, request_id: str) -> str:
    """
    Sanitizes SPARQL query strings by removing code blocks and other artifacts.
    
    Args:
        sparql_candidate: The raw SPARQL string to sanitize
        request_id: Request ID for logging
        
    Returns:
        Sanitized SPARQL string
    """
    if not sparql_candidate:
        return ""
        
    sanitized = re.sub(r'^\s*```sparql\s*(.*?)\s*```\s*$', r'\1', sparql_candidate, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    sanitized = re.sub(r'^\s*```\s*(.*?)\s*```\s*$', r'\1', sanitized, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    
    # Remove problematic Unicode characters that can interfere with SPARQL parsing
    sanitized = sanitized.replace('\u200B', '')  # Zero-width space
    sanitized = sanitized.replace('\u009f', '')  # Application Program Command (control character)
    sanitized = sanitized.replace('\u0080', '')  # Padding Character (control character)
    sanitized = sanitized.replace('\u0081', '')  # High Octet Preset (control character)

    # Remove any other control characters in the range 0x80-0x9F (Latin-1 Supplement control characters)
    import unicodedata
    sanitized = ''.join(char for char in sanitized if unicodedata.category(char) != 'Cc' or char in '\t\n\r')
    sanitized = sanitized.strip()
    
    if not re.search(r"(?i)^(PREFIX|SELECT|CONSTRUCT|ASK|DESCRIBE)", sanitized):
        logger.warning(f"[{request_id}] No SPARQL main keyword found in sanitized query. Returning as-is.")
    
    return sanitized


def add_limit_to_sparql_query(query: str, limit: int = 5) -> str:
    """
    Adds or replaces a LIMIT clause in a SPARQL query safely.
    
    Args:
        query: The SPARQL query
        limit: The limit value to set
        
    Returns:
        Query with LIMIT clause
    """
    limit_regex = re.compile(r'(LIMIT\s+\d+)(\s+OFFSET\s+\d+)?\s*$', re.IGNORECASE | re.DOTALL)
    if limit_regex.search(query):
        return limit_regex.sub(f'LIMIT {limit}\\2', query)
    else:
        return query.strip() + f"\nLIMIT {limit}"


def parse_llm_response_with_separator(raw_response: str, request_id: str, step_name: str) -> tuple[str, str]:
    """
    Parses LLM response that may contain reasoning and structured output sections.
    
    Args:
        raw_response: Raw response from LLM
        request_id: Request ID for logging
        step_name: Name of the step for logging
        
    Returns:
        Tuple of (reasoning_text, structured_output_text)
    """
    reasoning_text, structured_output_text = "", raw_response.strip()
    if OUTPUT_SEPARATOR in raw_response:
        reasoning_text, structured_output_text = (s.strip() for s in raw_response.split(OUTPUT_SEPARATOR, 1))
    return reasoning_text, structured_output_text


async def invoke_llm_and_parse(
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    prompt_template: ChatPromptTemplate,
    format_kwargs: dict,
    output_instructions_str: str,
    internal_reasoning_enabled: bool,
    few_shot_prompting_enabled: bool,
    request_id: str,
    step_name: str,
    adaptive_few_shot_enabled: bool = True,
    model_info_blocks: str = "",
    user_query: str = ""
) -> tuple[str, str, str]:
    """
    Invokes an LLM and parses the response with support for reasoning and few-shot prompting.

    Args:
        llm_instance: The LLM instance to use
        prompt_template: The prompt template
        format_kwargs: Variables for the template
        output_instructions_str: Instructions for output format
        internal_reasoning_enabled: Whether to include reasoning block
        few_shot_prompting_enabled: Whether to include few-shot examples
        request_id: Request ID for logging
        step_name: Name of the step for logging
        adaptive_few_shot_enabled: Whether to use adaptive few-shot selection (default: True)
        model_info_blocks: Semantic model content for adaptive selection
        user_query: User query for adaptive selection

    Returns:
        Tuple of (reasoning, structured_output, raw_response)
    """
    reasoning_block_to_inject = INTERNAL_REASONING_BLOCK_WITH_SEPARATOR if internal_reasoning_enabled else ""
    few_shot_examples_to_inject = ""

    # Determine which few-shot examples to use
    if few_shot_prompting_enabled:
        if adaptive_few_shot_enabled and step_name == "SPARQLGeneration" and user_query and model_info_blocks:
            # Use adaptive few-shot selection for SPARQL generation
            try:
                logger.info(f"[{request_id}] Using adaptive few-shot selection for SPARQL generation")
                adaptive_result = await get_adaptive_few_shot_examples(
                    user_query=user_query,
                    model_info_blocks=model_info_blocks,
                    llm_instance=llm_instance,
                    request_id=f"{request_id}_adaptive_fs"
                )
                few_shot_examples_to_inject = adaptive_result.get("formatted_examples", "")

                if few_shot_examples_to_inject:
                    predicted_ops = adaptive_result.get("predicted_operators", [])
                    logger.info(f"[{request_id}] Adaptive few-shot: predicted operators={predicted_ops}")
                else:
                    # Fallback to static examples if adaptive returns empty
                    logger.info(f"[{request_id}] Adaptive few-shot returned empty, using static fallback")
                    few_shot_examples_to_inject = get_static_fallback_examples()
            except Exception as e:
                logger.warning(f"[{request_id}] Adaptive few-shot failed: {e}, using static examples")
                few_shot_examples_to_inject = FEW_SHOT_EXAMPLES.get(step_name, "")
        else:
            # Use static few-shot examples for other steps or when adaptive is disabled
            few_shot_examples_to_inject = FEW_SHOT_EXAMPLES.get(step_name, "")

    if few_shot_examples_to_inject:
        logger.info(f"[{request_id}] Injecting few-shot examples for step: {step_name}")
    
    all_format_kwargs = {
        **format_kwargs,
        "optional_internal_reasoning_block": reasoning_block_to_inject,
        "optional_few_shot_examples": few_shot_examples_to_inject,
        "final_output_instructions": output_instructions_str
    }

    # Ensure optional_example_instances_block is handled even if empty
    if "optional_example_instances_block" not in all_format_kwargs:
        all_format_kwargs["optional_example_instances_block"] = ""
    
    prompt_messages = prompt_template.format_messages(**all_format_kwargs)
    prompt_str = "".join([m.content for m in prompt_messages])

    # For SPARQL generation, log the complete prompt to verify instance data inclusion
    if step_name == "SPARQLGeneration":
        logger.info(f"[{request_id}] === COMPLETE SPARQL GENERATION PROMPT ===\n{prompt_str}")
    else:
        logger.info(f"[{request_id}] === FULL PROMPT SENT TO LLM ({step_name}) ===\n{prompt_str[:1000]}...")
    
    raw_response = await asyncio.to_thread(llm_instance.invoke, prompt_str)
    logger.info(f"[{request_id}] === RAW LLM RESPONSE ({step_name}) ===\n{raw_response}")
    
    reasoning, structured_output = parse_llm_response_with_separator(raw_response, request_id, step_name)
    
    if internal_reasoning_enabled and reasoning:
        logger.info(f"[{request_id}] Internal Reasoning ({step_name}):\n{reasoning}")
    
    return reasoning, structured_output, raw_response


async def generate_sparql_query(
    user_query: str,
    model_info_blocks: str,
    model_check_hints: str,
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    internal_reasoning_enabled: bool = False,
    few_shot_prompting_enabled: bool = False,
    request_id: str = "N/A_sparql_gen",
    example_instances_block: str = "",
    adaptive_few_shot_enabled: bool = True
) -> dict:
    """
    Generates a SPARQL query based on user query and model information.

    Args:
        user_query: The user's natural language query
        model_info_blocks: Information about available models
        model_check_hints: Hints from model validation
        llm_instance: The LLM instance to use
        internal_reasoning_enabled: Whether to enable internal reasoning
        few_shot_prompting_enabled: Whether to enable few-shot prompting
        request_id: Request ID for logging
        example_instances_block: Optional instance data for query generation
        adaptive_few_shot_enabled: Whether to use adaptive few-shot selection (default: True)

    Returns:
        Dictionary containing the generated query and metadata
    """
    logger.info(f"[{request_id}] Generating SPARQL query for: '{user_query[:100]}...'")
    logger.info(f"[{request_id}] Few-shot config: enabled={few_shot_prompting_enabled}, adaptive={adaptive_few_shot_enabled}")

    reasoning, structured_output, raw_response = await invoke_llm_and_parse(
        llm_instance,
        SPARQL_GENERATOR_PROMPT_MULTI_MODEL,
        {
            "query": user_query,
            "model_info_blocks": model_info_blocks,
            "model_check_hints": model_check_hints,
            "optional_example_instances_block": example_instances_block
        },
        OUTPUT_INSTRUCTIONS_GENERATE_SPARQL,
        internal_reasoning_enabled,
        few_shot_prompting_enabled,
        request_id,
        "SPARQLGeneration",
        adaptive_few_shot_enabled=adaptive_few_shot_enabled,
        model_info_blocks=model_info_blocks,
        user_query=user_query
    )
    
    sanitized_output = robust_sparql_sanitize(structured_output, request_id)
    final_sparql_query = add_correct_prefixes(sanitized_output, model_info_blocks)
    
    logger.info(f"[{request_id}] Final, prefix-corrected SPARQL Query:\n{final_sparql_query}")
    
    return {
        "sparql_query": final_sparql_query, 
        "reasoning": reasoning, 
        "raw_response": raw_response
    }


async def apply_agentic_reasoning_to_sparql(
    user_query: str,
    model_info_blocks: str,
    model_check_hints: str,
    generated_query: str,
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    request_id: str
) -> str:
    """
    Applies agentic reasoning to review and potentially correct a SPARQL query.
    
    Args:
        user_query: The original user query
        model_info_blocks: Information about available models
        model_check_hints: Hints from model validation
        generated_query: The initially generated SPARQL query
        llm_instance: The LLM instance to use
        request_id: Request ID for logging
        
    Returns:
        The potentially corrected SPARQL query
    """
    logger.info(f"[{request_id}] Applying agentic reasoning to SPARQL query...")
    
    try:
        import json
        
        prompt_vars = {
            "query": user_query, 
            "model_info_blocks": model_info_blocks, 
            "model_check_hints": model_check_hints, 
            "generated_sparql_query": generated_query
        }
        
        formatted_prompt = SPARQL_AGENTIC_REASONER_PROMPT.format_prompt(**prompt_vars).to_string()
        response_str = await asyncio.to_thread(llm_instance.invoke, formatted_prompt)
        
        json_match = re.search(r"\{[\s\S]*\}", response_str)
        if json_match:
            reasoning_data = json.loads(json_match.group(0))
            if reasoning_data.get("assessment") != "korrekt" and reasoning_data.get("corrected_query"):
                logger.info(f"[{request_id}] Agentic correction applied to SPARQL query.")
                return reasoning_data["corrected_query"]
        else:
            logger.warning(f"[{request_id}] Agentic reasoning response could not be parsed.")
    except Exception as e:
        logger.error(f"[{request_id}] Error during agentic reasoning: {e}", exc_info=True)
    
    return generated_query


async def correct_sparql_syntax_errors(
    workspace_id: str,
    failed_query: str, 
    user_query: str,
    semantic_models_content: str,
    syntax_error_details: str,
    llm_instance: Union[OllamaLLM, OpenAILLM, DeepSeekLLM],
    internal_reasoning_enabled: bool = False,
    few_shot_prompting_enabled: bool = False,
    request_id: str = "syntax_correction"
) -> Dict[str, Any]:
    """
    Corrects SPARQL syntax errors using an LLM.
    
    Args:
        workspace_id: The workspace ID
        failed_query: The query with syntax errors
        user_query: The original user query
        semantic_models_content: Content of semantic models
        syntax_error_details: Details about the syntax error
        llm_instance: The LLM instance to use
        internal_reasoning_enabled: Whether to enable internal reasoning
        few_shot_prompting_enabled: Whether to enable few-shot prompting
        request_id: Request ID for logging
        
    Returns:
        Dictionary with correction results
    """
    logger.info(f"[{request_id}] Attempting to correct SPARQL syntax errors")
    
    try:
        reasoning, structured_output, raw_response = await invoke_llm_and_parse(
            llm_instance,
            SPARQL_SYNTAX_ERROR_CORRECTION_PROMPT,
            {
                "user_query": user_query,
                "semantic_models_content": semantic_models_content,
                "failed_query": failed_query,
                "syntax_error_details": syntax_error_details
            },
            OUTPUT_INSTRUCTIONS_SYNTAX_CORRECTION,
            internal_reasoning_enabled,
            few_shot_prompting_enabled,
            request_id,
            "SyntaxCorrection"
        )
        
        corrected_query = robust_sparql_sanitize(structured_output, request_id)
        
        if not corrected_query:
            logger.error(f"[{request_id}] LLM returned empty corrected query")
            return {
                "success": False,
                "error": "LLM returned empty corrected query",
                "corrected_query": None
            }
        
        # Add correct prefixes
        corrected_query_with_prefixes = add_correct_prefixes(
            corrected_query, semantic_models_content
        )
        
        logger.info(f"[{request_id}] Generated corrected query: {corrected_query_with_prefixes[:100]}...")
        
        # Note: Syntax validation would be done by the calling code
        return {
            "success": True,
            "corrected_query": corrected_query_with_prefixes,
            "error": None,
            "reasoning": reasoning
        }
            
    except Exception as e:
        logger.error(f"[{request_id}] Error during syntax correction: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Error during syntax correction: {str(e)}",
            "corrected_query": None
        }