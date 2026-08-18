# backend/app/utils.py

import asyncio
import codecs
import json
import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, AsyncGenerator
from uuid import uuid4
import datetime as dt # For format_sse_event
from collections import Counter
from rdflib import Graph, URIRef, Literal, BNode, RDFS, RDF, OWL, Namespace
from .config import DATA_DIR

# Setup a logger for this module
logger = logging.getLogger(__name__)


def parse_ttl_to_graph_json(file_path: Path, request_id: str) -> Optional[Dict[str, List[Dict]]]:
    """
    Parses a Turtle file and converts it into a JSON structure
    suitable for graph visualization libraries like React Flow.
    Returns a dictionary with 'nodes' and 'edges' or None on failure.
    Classifies nodes as 'class', 'property', or 'literal' based on RDF type.
    """
    if not file_path.exists():
        logger.error(f"[{request_id}] File not found for graph parsing: {file_path}")
        return None

    try:
        g = Graph()
        g.parse(str(file_path), format="turtle")

        nodes = {}
        edges = []
        node_original_objects = {}  # Store original RDF objects for type detection

        def get_node_id(node: Union[URIRef, BNode, Literal]) -> str:
            if isinstance(node, URIRef):
                return str(node).split('#')[-1].split('/')[-1]
            elif isinstance(node, BNode):
                return str(node)
            return str(node)

        def determine_node_type(node_obj: Union[URIRef, BNode, Literal], g: Graph) -> str:
            """Determine the visual type of a node based on its RDF characteristics."""
            if isinstance(node_obj, Literal):
                return "literal"

            if isinstance(node_obj, (URIRef, BNode)):
                # Check if it's explicitly typed as a class
                for type_obj in g.objects(node_obj, RDF.type):
                    type_str = str(type_obj).lower()
                    if 'class' in type_str or type_obj == OWL.Class or type_obj == RDFS.Class:
                        return "class"
                    if 'property' in type_str or type_obj in (OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property):
                        return "property"

                # Check if this node is used as a predicate (then it's a property)
                node_uri = node_obj if isinstance(node_obj, URIRef) else None
                if node_uri:
                    for _, p, _ in g:
                        if p == node_uri:
                            return "property"

                # Default to class for URI nodes
                return "class"

            return "default"

        for s, p, o in g:
            source_id = get_node_id(s)
            target_id = get_node_id(o)

            # Store original objects for type detection
            if source_id not in node_original_objects:
                node_original_objects[source_id] = s
            if target_id not in node_original_objects:
                node_original_objects[target_id] = o

            for node_obj in [s, o]:
                node_id = get_node_id(node_obj)
                if node_id not in nodes:
                    node_type = determine_node_type(node_obj, g)
                    # Use position (0,0) as Dagre will calculate proper positions
                    nodes[node_id] = {
                        "id": node_id,
                        "type": "custom",
                        "data": {
                            "label": node_id,
                            "nodeType": node_type
                        },
                        "position": {"x": 0, "y": 0}
                    }

            predicate_label = get_node_id(p)

            edge_id = f"edge-{source_id}-{target_id}-{predicate_label}"
            edges.append({
                "id": edge_id,
                "source": source_id,
                "target": target_id,
                "label": predicate_label,
                "type": "custom"
            })

        return {"nodes": list(nodes.values()), "edges": edges}

    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse TTL file {file_path} into graph JSON: {e}", exc_info=True)
        return None



def parse_ttl_to_clean_triples(file_path: Path, request_id: str) -> Optional[str]:
    """
    Parses a Turtle (.ttl) file and returns a clean, readable string of its triples.
    Returns None if parsing fails.

    Note: Extracts prefixes from the original file and explicitly binds them to avoid
    RDFLib generating numbered prefixes (e.g., geo1: instead of geo:) due to conflicts
    with its default namespace bindings.
    """
    if not file_path.exists():
        logger.error(f"[{request_id}] File not found for parsing: {file_path}")
        return None

    try:
        # Step 1: Read file content and extract prefixes before parsing
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()

        # Extract @prefix declarations from the TTL file
        prefix_pattern = re.compile(r'@prefix\s+(\w+):\s*<([^>]+)>\s*\.', re.IGNORECASE)
        file_prefixes = prefix_pattern.findall(file_content)

        # Step 2: Parse the graph
        g = Graph()
        g.parse(str(file_path), format="turtle")

        # Step 3: Explicitly bind extracted prefixes (overrides RDFLib defaults)
        # This prevents numbered prefixes like geo1: when there's a conflict
        for prefix, uri in file_prefixes:
            g.bind(prefix, Namespace(uri), override=True, replace=True)

        if len(g) == 0:
            logger.warning(f"[{request_id}] Parsed graph from {file_path} is empty.")
            return "# Das Modell ist leer."

        # Hilfsfunktion, um URIs zu kürzen oder Labels zu verwenden
        def get_node_representation(node):
            if isinstance(node, URIRef):
                # Versuche, ein rdfs:label zu finden
                label = g.value(subject=node, predicate=RDFS.label)
                if label:
                    return f'"{label}"' # In Anführungszeichen für Klarheit
                # Fallback: Prefixed Name
                return node.n3(g.namespace_manager)
            return node.n3()

        triple_strings = []
        for s, p, o in g:
            subj_repr = get_node_representation(s)
            pred_repr = get_node_representation(p)
            obj_repr = get_node_representation(o)
            triple_strings.append(f"{subj_repr} {pred_repr} {obj_repr} .")

        return "\n".join(triple_strings)

    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse TTL file {file_path}: {e}", exc_info=True)
        return f"# Fehler beim Parsen des Modells: {e}"


def decode_unicode_escapes(data: Union[str, List[Any], Dict[Any, Any], None]) -> Union[str, List[Any], Dict[Any, Any], None]:
    """
    Recursively decodes Python-style unicode escape sequences in strings,
    lists, or dictionaries. E.g., "\\u00fc" becomes "ü".
    This is useful for strings that have been json.loads'd but originated
    from an LLM or other source that produced literal backslash-u sequences.
    """
    if isinstance(data, str):
        if '\\u' in data or '\\U' in data:
            try:
                return codecs.decode(data, 'unicode_escape')
            except UnicodeDecodeError as e:
                logger.warning(f"UnicodeDecodeError while decoding '{data[:100]}...': {e}. Returning original string.")
                return data
            except Exception as e:
                logger.error(f"Unexpected error in decode_unicode_escapes for string '{data[:100]}...': {e}", exc_info=True)
                return data
        else:
            return data
    elif isinstance(data, list):
        return [decode_unicode_escapes(item) for item in data]
    elif isinstance(data, dict):
        return {
            decode_unicode_escapes(k) if isinstance(k, str) else k: decode_unicode_escapes(v)
            for k, v in data.items()
        }
    return data

def load_templates_for_workspace(workspace_id: str, request_id_str: str) -> List[Dict[str, Any]]:
    workspace_template_dir = DATA_DIR / workspace_id / "request_templates"
    logger.info(f"[{workspace_id}] Attempting to load templates from directory {workspace_template_dir}. Request: {request_id_str}")

    if not workspace_template_dir.exists() or not workspace_template_dir.is_dir():
        logger.warning(f"[{workspace_id}] Templates directory not found at {workspace_template_dir}. Returning empty list. Request: {request_id_str}")
        return []

    json_files = list(workspace_template_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"[{workspace_id}] No .json files found in {workspace_template_dir}. Returning empty list. Request: {request_id_str}")
        return []

    templates_file_path_to_load = json_files[0]
    logger.info(f"[{workspace_id}] Found template file to load: {templates_file_path_to_load}. Request: {request_id_str}")
    
    try:
        with open(templates_file_path_to_load, 'r', encoding='utf-8') as f:
            templates_data = json.load(f)
            if not isinstance(templates_data, list):
                logger.error(f"[{workspace_id}] Templates file at {templates_file_path_to_load} does not contain a JSON list. Content type: {type(templates_data)}. Request: {request_id_str}")
                return []
            logger.info(f"[{workspace_id}] Successfully loaded templates. Number of templates: {len(templates_data)}. First template ID (if any): {templates_data[0].get('id') if templates_data and len(templates_data) > 0 else 'N/A'}. Request: {request_id_str}")
            return templates_data
    except json.JSONDecodeError as e:
        logger.error(f"[{workspace_id}] Error decoding JSON from {templates_file_path_to_load}: {e}. Request: {request_id_str}")
        return []
    except Exception as e:
        logger.error(f"[{workspace_id}] An unexpected error occurred while loading templates from {templates_file_path_to_load}: {e}. Request: {request_id_str}")
        return []

async def format_sse_event(data: Union[str, dict], event_type: Optional[str] = None, is_error: bool = False) -> str:
    message_id = str(uuid4())
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    
    if isinstance(data, dict):
        payload_data = data.copy() 
        payload_data.setdefault('id', message_id)
        payload_data.setdefault('timestamp', timestamp)
        payload_data.setdefault('is_error', is_error)
    else:
        payload_data = {
            "id": message_id,
            "message": str(data),
            "timestamp": timestamp,
            "is_error": is_error
        }
    
    json_data = json.dumps(payload_data)
    
    sse_event_parts = []
    if event_type:
        sse_event_parts.append(f"event: {event_type}")
    sse_event_parts.append(f"data: {json_data}")
    return "\n".join(sse_event_parts) + "\n\n"


async def stream_message_fake(message: str, sender: str, step_id: str, request_timestamp: str, 
                              delay_between_chars: float = 0.02, delay_between_words: float = 0.1) -> AsyncGenerator[str, None]:
    """Fake-stream a system message character by character to simulate typing effect."""
    message_id = str(uuid4())
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    
    # Start streaming event
    start_data = {
        "id": message_id,
        "sender": sender,
        "message": "",
        "step_id": step_id,
        "request_timestamp": request_timestamp,
        "timestamp": timestamp,
        "is_streaming": True,
        "stream_status": "start"
    }
    yield await format_sse_event(start_data, "message_stream_start")
    
    # Stream characters while preserving line breaks and formatting
    accumulated_message = ""
    
    for char_idx, char in enumerate(message):
        accumulated_message += char
        
        chunk_data = {
            "id": message_id,
            "sender": sender,
            "message": accumulated_message,
            "step_id": step_id,
            "request_timestamp": request_timestamp,
            "timestamp": timestamp,
            "is_streaming": True,
            "stream_status": "chunk"
        }
        yield await format_sse_event(chunk_data, "message_stream_chunk")
        
        # Different delays for different characters
        if char == '\n':
            await asyncio.sleep(delay_between_words * 2)  # Longer pause at line breaks
        elif char == ' ':
            await asyncio.sleep(delay_between_words)  # Normal pause at spaces
        else:
            await asyncio.sleep(delay_between_chars)  # Fast for regular characters
    
    # End streaming event
    end_data = {
        "id": message_id,
        "sender": sender,
        "message": accumulated_message,
        "step_id": step_id,
        "request_timestamp": request_timestamp,
        "timestamp": timestamp,
        "is_streaming": False,
        "stream_status": "end"
    }
    yield await format_sse_event(end_data, "message_stream_end")


async def stream_llm_response(llm_instance, prompt: str, sender: str, step_id: str, 
                             request_timestamp: str) -> AsyncGenerator[str, None]:
    """Stream LLM response token by token."""
    message_id = str(uuid4())
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    
    # Start streaming event
    start_data = {
        "id": message_id,
        "sender": sender,
        "message": "",
        "step_id": step_id,
        "request_timestamp": request_timestamp,
        "timestamp": timestamp,
        "is_streaming": True,
        "stream_status": "start"
    }
    yield await format_sse_event(start_data, "message_stream_start")
    
    # Check if LLM supports streaming
    accumulated_message = ""
    
    if hasattr(llm_instance, 'stream_invoke'):
        # Real streaming from LLM
        try:
            async for token in llm_instance.stream_invoke(prompt):
                accumulated_message += token
                
                chunk_data = {
                    "id": message_id,
                    "sender": sender,
                    "message": accumulated_message,
                    "step_id": step_id,
                    "request_timestamp": request_timestamp,
                    "timestamp": timestamp,
                    "is_streaming": True,
                    "stream_status": "chunk"
                }
                yield await format_sse_event(chunk_data, "message_stream_chunk")
        except Exception as e:
            logger.error(f"Error during LLM streaming: {e}")
            # Fallback to non-streaming
            response = await asyncio.to_thread(llm_instance.invoke, prompt)
            accumulated_message = response.content if hasattr(response, 'content') else str(response)
    else:
        # Fallback: Get full response and fake-stream it
        try:
            response = await asyncio.to_thread(llm_instance.invoke, prompt)
            full_message = response.content if hasattr(response, 'content') else str(response)
            
            # Fake stream the response
            words = full_message.split()
            for word_idx, word in enumerate(words):
                for char in word:
                    accumulated_message += char
                    
                    chunk_data = {
                        "id": message_id,
                        "sender": sender,
                        "message": accumulated_message,
                        "step_id": step_id,
                        "request_timestamp": request_timestamp,
                        "timestamp": timestamp,
                        "is_streaming": True,
                        "stream_status": "chunk"
                    }
                    yield await format_sse_event(chunk_data, "message_stream_chunk")
                    await asyncio.sleep(0.02)  # 20ms delay between characters
                
                # Add space after word (except for last word)
                if word_idx < len(words) - 1:
                    accumulated_message += " "
                    chunk_data = {
                        "id": message_id,
                        "sender": sender,
                        "message": accumulated_message,
                        "step_id": step_id,
                        "request_timestamp": request_timestamp,
                        "timestamp": timestamp,
                        "is_streaming": True,
                        "stream_status": "chunk"
                    }
                    yield await format_sse_event(chunk_data, "message_stream_chunk")
                    await asyncio.sleep(0.1)  # 100ms delay between words
        except Exception as e:
            logger.error(f"Error during LLM invoke: {e}")
            accumulated_message = f"Fehler bei der LLM-Antwort: {str(e)}"
    
    # End streaming event
    end_data = {
        "id": message_id,
        "sender": sender,
        "message": accumulated_message,
        "step_id": step_id,
        "request_timestamp": request_timestamp,
        "timestamp": timestamp,
        "is_streaming": False,
        "stream_status": "end"
    }
    yield await format_sse_event(end_data, "message_stream_end")
