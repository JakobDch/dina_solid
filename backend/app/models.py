"""
Database tables and API payload models.

The dataset itself lives in the Solid dataspace, so nothing here mirrors it.
What is persisted is only what the application needs to hold between requests:
workspaces, chat sessions with their messages, and the SPARQL example corpus
used for few-shot prompting.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from sqlmodel import JSON, Column, Field, Relationship, SQLModel


# =============================================================================
# WORKSPACE
# =============================================================================
class WorkspaceBase(SQLModel):
    title: str
    description: Optional[str] = None


class Workspace(SQLModel, table=True):
    """A container grouping the chat sessions of one line of work."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    title: str
    description: Optional[str] = None
    created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    chat_sessions: List["ChatSession"] = Relationship(
        back_populates="workspace",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class WorkspaceCreate(SQLModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    # Accepted for compatibility with the existing frontend. Only the title and
    # description are copied - a workspace holds no files of its own.
    clone_from_id: Optional[str] = None


# =============================================================================
# CHAT SESSIONS
# =============================================================================
class ChatSession(SQLModel, table=True):
    """A conversation, holding the context that follow-up questions rely on."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    workspace_id: str = Field(foreign_key="workspace.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Context established by the first successful query.
    initial_query: str
    selected_models: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    model_info_blocks: str  # Semantic model content of the initial query
    model_check_hints: str  # Model reasoning of the initial query

    # Result of the most recent query. A JSON column is used because Comunica
    # returns either a list of bindings or the full nested result structure.
    last_sparql_query: Optional[str] = None
    last_sparql_results: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None, sa_column=Column(JSON)
    )
    last_sparql_variables: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))

    is_active: bool = Field(default=True)

    # History kept so later steps can refer back to earlier ones. Large result
    # sets are cached out of band and only sampled here.
    results_history_data: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))

    last_visualization_code: Optional[str] = None
    visualization_history: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))

    last_calculation_code: Optional[str] = None
    last_calculation_results: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    calculation_history: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))

    # Cached catalog searches, so a follow-up question need not search again.
    catalog_search_history: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))

    # Which catalog of the dataspace this conversation is bound to.
    solid_mode: bool = Field(default=False)
    catalog_id: Optional[str] = None
    catalog_url: Optional[str] = None

    workspace: "Workspace" = Relationship(back_populates="chat_sessions")
    messages: List["ChatSessionMessage"] = Relationship(
        back_populates="session",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ChatSessionMessage(SQLModel, table=True):
    """A single message inside a chat session."""

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    session_id: str = Field(foreign_key="chatsession.id", index=True)
    message: str
    is_user_message: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Populated for assistant messages that carry a query result.
    sparql_query: Optional[str] = None
    sparql_results: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    step_id: Optional[str] = None

    session: ChatSession = Relationship(back_populates="messages")


class CreateChatSessionRequest(SQLModel):
    workspace_id: str
    initial_query: str
    selected_models: List[str]
    model_info_blocks: str
    model_check_hints: str
    sparql_query: Optional[str] = None
    sparql_results: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None
    sparql_variables: Optional[List[str]] = None


class ChatSessionRead(SQLModel):
    id: str
    workspace_id: str
    created_at: datetime
    last_activity: datetime
    initial_query: str
    selected_models: List[str]
    is_active: bool


class ComunicaResultsRequest(SQLModel):
    """Results posted back by the browser after it ran a query with Comunica.

    The backend does not execute SPARQL itself: it hands the query and the
    dataset URLs to the client, which queries the pods directly and returns the
    results here so the agent can continue its plan.
    """

    session_id: str = Field(description="Agent session ID")
    step_number: int = Field(description="Current plan step number")
    results: List[Dict[str, Any]] = Field(description="Query results from Comunica")
    variables: List[str] = Field(description="SPARQL variable names")
    total: int = Field(description="Total number of results")

    # Supplied so the session can be created if it does not exist yet.
    workspace_id: Optional[str] = Field(default=None, description="Workspace the session belongs to")
    user_query: Optional[str] = Field(default=None, description="Original user query")
    sparql_query: Optional[str] = Field(default=None, description="The query that was executed")
    catalog_id: Optional[str] = Field(default=None, description="Selected catalog ID")
    catalog_url: Optional[str] = Field(default=None, description="Selected catalog URL")


# =============================================================================
# SPARQL EXAMPLE CORPUS
# =============================================================================
class SPARQLCorpusEntry(SQLModel, table=True):
    """A query example used for few-shot prompting, shared across workspaces."""

    __tablename__ = "sparql_corpus_entries"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)

    natural_language_query: str = Field(..., description="The original question")
    sparql_query: str = Field(..., description="The corresponding SPARQL query")

    # Used to pick examples that match the operators a new query is likely to need.
    sparql_operators: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    complexity: str = Field(default="medium", description="basic, intermediate or advanced")

    semantic_models: List[str] = Field(
        default_factory=list, sa_column=Column(JSON), description="Semantic models used"
    )
    semantic_models_content: Optional[str] = Field(default=None, description="Full RDF of those models")
    is_multi_model: bool = Field(default=False, description="Whether several models are involved")

    source: str = Field(default="manual", description="manual, learned or migrated")
    theme: Optional[str] = Field(default=None, description="Optional category")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    usage_count: int = Field(default=0, description="How often this example was used")
    success_rate: float = Field(default=0.0, description="Success rate when used as an example")


class SPARQLCorpusEntryCreate(SQLModel):
    natural_language_query: str
    sparql_query: str
    semantic_models: List[str] = Field(default_factory=list)
    semantic_models_content: Optional[str] = None
    theme: Optional[str] = None
    source: str = Field(default="manual")


class SPARQLCorpusEntryRead(SQLModel):
    id: str
    natural_language_query: str
    sparql_query: str
    sparql_operators: List[str]
    complexity: str
    semantic_models: List[str]
    is_multi_model: bool
    source: str
    theme: Optional[str]
    created_at: datetime
    updated_at: datetime
    usage_count: int
    success_rate: float


class SPARQLCorpusEntryUpdate(SQLModel):
    natural_language_query: Optional[str] = None
    sparql_query: Optional[str] = None
    semantic_models: Optional[List[str]] = None
    semantic_models_content: Optional[str] = None
    theme: Optional[str] = None


Workspace.model_rebuild(force=True)
ChatSession.model_rebuild(force=True)
ChatSessionMessage.model_rebuild(force=True)
