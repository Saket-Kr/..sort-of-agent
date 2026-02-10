"""Tool input/output schemas."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """Single web search result."""

    title: str
    url: str
    snippet: str
    source: Optional[str] = None


class WebSearchInput(BaseModel):
    """Input for web search tool."""

    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of search queries to execute",
    )


class WebSearchOutput(BaseModel):
    """Output from web search tool."""

    results: list[WebSearchResult]
    query_count: int
    total_results: int


class TaskBlockSearchResult(BaseModel):
    """Single task block search result."""

    block_id: str
    name: str
    action_code: str
    description: Optional[str] = None
    inputs: list[dict] = Field(default_factory=list)
    outputs: list[dict] = Field(default_factory=list)
    relevance_score: float = 0.0


class TaskBlockSearchInput(BaseModel):
    """Input for task block search tool."""

    queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of queries to search for task blocks",
    )


class TaskBlockSearchOutput(BaseModel):
    """Output from task block search tool."""

    results: list[TaskBlockSearchResult]
    query_count: int
    total_results: int


class ClarifyInput(BaseModel):
    """Input for clarification tool."""

    questions: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="Questions to ask the user for clarification",
    )


class ClarifyOutput(BaseModel):
    """Output from clarification tool."""

    clarification_id: str
    questions: list[str]
    status: Literal["awaiting_response"] = "awaiting_response"


class ClarificationResponse(BaseModel):
    """User's response to clarification request."""

    clarification_id: str
    response: str
