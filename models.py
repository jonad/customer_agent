from pydantic import BaseModel
from typing import Optional, Literal
from enum import Enum


class CustomerInquiryRequest(BaseModel):
    customer_inquiry: str


class CustomerInquiryResponse(BaseModel):
    original_inquiry: str
    category: str
    suggested_response: str


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
