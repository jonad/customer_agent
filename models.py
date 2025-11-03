from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum


class CustomerInquiryRequest(BaseModel):
    customer_inquiry: str


class CustomerInquiryResponse(BaseModel):
    original_inquiry: str
    category: str
    suggested_response: str


class UnifiedInquiryRequest(BaseModel):
    """Request model for unified process-inquiry endpoint with routing"""
    message: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class UnifiedInquiryResponse(BaseModel):
    """Unified response for all query types (SQL, document search, customer service)"""
    query_type: str  # "sql_query", "document_search", or "customer_service"
    original_message: str
    response_data: dict  # Contains type-specific response data
    session_id: Optional[str] = None


class StreamingChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None


class StreamEventType(str, Enum):
    PROCESSING = "processing"
    CATEGORIZING = "categorizing"
    RESPONDING = "responding"
    PARTIAL_RESPONSE = "partial_response"
    FINAL_RESPONSE = "final_response"
    ERROR = "error"
    STATUS = "status"
    # SQL Query Event Types
    SQL_ROUTING = "sql_routing"
    SQL_SCHEMA_RETRIEVING = "sql_schema_retrieving"
    SQL_GENERATING = "sql_generating"
    SQL_VALIDATING = "sql_validating"
    SQL_EXECUTING = "sql_executing"
    # Document Search Event Types
    DOC_ANALYZING = "doc_analyzing"
    DOC_RETRIEVING = "doc_retrieving"
    DOC_RANKING = "doc_ranking"
    DOC_SYNTHESIZING = "doc_synthesizing"


class StreamingMessage(BaseModel):
    event_type: StreamEventType
    data: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: Optional[dict] = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    user_id: Optional[str] = None
    feedback: Optional[str] = None


class ChatHistoryRequest(BaseModel):
    session_id: str
    limit: Optional[int] = 50


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessage]
    total_count: int


class SessionCreate(BaseModel):
    user_id: str
    title: Optional[str] = "New Chat"


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: Optional[int] = 0


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total_count: int


class UpdateTitleRequest(BaseModel):
    title: str


class MessageFeedbackRequest(BaseModel):
    feedback: Optional[Literal["like", "dislike"]] = None


class DeleteSessionResponse(BaseModel):
    session_id: str
    deleted: bool
    messages_deleted: int


class SqlQueryResponse(BaseModel):
    original_question: str
    generated_sql: Optional[str] = None
    query_results: Optional[list[dict]] = None
    natural_language_answer: str
    error: Optional[str] = None


# Document Search Models
class DocumentUploadRequest(BaseModel):
    title: str
    content: str
    file_type: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    file_type: Optional[str] = None
    metadata: Optional[dict] = None
    content_length: Optional[int] = None
    created_at: str
    updated_at: Optional[str] = None


class DocumentDetailResponse(BaseModel):
    document_id: str
    title: str
    content: str
    file_type: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: str
    updated_at: Optional[str] = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total_count: int
    limit: int
    offset: int


class DocumentSearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10


class SearchResultDocument(BaseModel):
    document_id: str
    title: str
    file_type: Optional[str] = None
    metadata: Optional[dict] = None
    snippet: str
    relevance_score: Optional[float] = None
    created_at: str


class DocumentSearchResponse(BaseModel):
    original_query: str
    retrieved_documents: list[SearchResultDocument]
    answer: str
    total_results: int
