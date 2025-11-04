# https://medium.com/@zakinabdul.jzl/orchestrating-multi-agent-workflows-with-google-adk-and-fastapi-e6b4b1a22c90

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from fastapi import FastAPI, APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from models import (
    CustomerInquiryRequest, CustomerInquiryResponse, StreamingChatRequest,
    StreamingMessage, StreamEventType, ChatMessage, ChatHistoryRequest,
    ChatHistoryResponse, SessionCreate, SessionResponse, SessionListResponse,
    UpdateTitleRequest, MessageFeedbackRequest, DeleteSessionResponse,
    DocumentUploadRequest, DocumentResponse, DocumentDetailResponse,
    DocumentListResponse, DocumentSearchRequest, DocumentSearchResponse,
    UnifiedInquiryRequest, UnifiedInquiryResponse
)
import asyncio
from datetime import datetime, timedelta
from chat_history_postgres import ChatHistoryServicePostgres
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from agents.customer_agent import CustomerAgentOrchestrator
from agents.sql_agent import SqlAgentOrchestrator
from agents.document_agent import DocumentAgentOrchestrator
from agents.router import RouterOrchestrator
from sql_query_service import SqlQueryService
from embedding_service import embedding_service
from google.genai import types
import json
import re
import uuid
import os
from contextlib import asynccontextmanager

# SQLite DB init for Google ADK
DB_URL = "sqlite:///./multi_agent_data.db"
APP_NAME = "CustomerInquiryProcessor"


# Create a lifespan event to initialize and clean up the session service
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    print("Application starting up...")
    # Initialize the DatabaseSessionService instance and store it in app.state
    try:
        app.state.session_service = DatabaseSessionService(db_url=DB_URL)
        print("Database session service initialized successfully.")
    except Exception as e:
        print("Database session service initialized failed.")
        print(e)

    # Initialize chat history database (PostgreSQL)
    try:
        await chat_history.init_db()
        print("Chat history database initialized successfully (PostgreSQL).")
    except Exception as e:
        print(f"Chat history database initialization failed: {e}")

    yield  # This is where the application runs, handling requests

    # Shutdown code
    print("Application shutting down...")

    # Close chat history database connections
    try:
        await chat_history.close()
        print("Chat history database connections closed.")
    except Exception as e:
        print(f"Error closing chat history connections: {e}")

    # Close SQL query service connections
    try:
        await sql_query_service.close()
        print("SQL query service connections closed.")
    except Exception as e:
        print(f"Error closing SQL query service connections: {e}")


# FastAPI application setup
app = FastAPI(
    title="Customer Inquiry Processor",
    description="Multi-agent system for processing customer inquiries",
    version="1.0.0",
    lifespan=lifespan,
)
# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Initializing the Orchestrators and Services (PostgreSQL only)
customer_agent = CustomerAgentOrchestrator()
sql_agent = SqlAgentOrchestrator()
document_agent = DocumentAgentOrchestrator()
router_agent = RouterOrchestrator()
chat_history = ChatHistoryServicePostgres()
sql_query_service = SqlQueryService()
router = APIRouter()


async def format_sse_message(event_type: StreamEventType, data: str = None, session_id: str = None, metadata: dict = None) -> str:
    """Format a Server-Sent Events message"""
    message = StreamingMessage(
        event_type=event_type,
        data=data,
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
        metadata=metadata
    )
    return f"data: {message.model_dump_json()}\n\n"


async def stream_sql_query_events(user_question: str, session_id: str, user_id: str):
    """Stream SQL query processing events in real-time"""
    try:
        # Get database session service from application state
        session_service: DatabaseSessionService = app.state.session_service

        # Store user message in chat history
        user_message = ChatMessage(
            role="user",
            content=user_question,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        await chat_history.store_message(user_message)
        await chat_history.update_session_timestamp(session_id)

        # Send initial status
        yield await format_sse_message(
            StreamEventType.STATUS,
            "Processing SQL query...",
            session_id
        )

        # Get or create ADK session
        current_session = None
        try:
            current_session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Session retrieval failed: {e}")

        if current_session is None:
            current_session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )

        # Initialize SQL Generation Runner
        yield await format_sse_message(StreamEventType.SQL_GENERATING, "Generating SQL query...", session_id)

        # Using "agents" app_name to match the inferred app_name from LlmAgent's package location
        runner = Runner(
            app_name="agents",
            agent=sql_agent.sql_generation_agent,
            session_service=session_service,
        )

        user_message_adk = types.Content(
            role="user", parts=[types.Part.from_text(text=user_question)]
        )

        # Run SQL generation pipeline
        events = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message_adk,
        )

        validation_result = None
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                final_content = event.content.parts[0].text
                cleaned_response = re.sub(
                    r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                )
                try:
                    validation_result = json.loads(cleaned_response)
                except json.JSONDecodeError as e:
                    yield await format_sse_message(
                        StreamEventType.ERROR,
                        "Failed to parse SQL validation result",
                        session_id
                    )
                    return

        # SqlGeneratorAgent returns {"sql_query": "...", "explanation": "..."}
        if not validation_result or not validation_result.get("sql_query"):
            error_msg = "Failed to generate SQL query"
            yield await format_sse_message(
                StreamEventType.ERROR,
                f"SQL generation failed: {error_msg}",
                session_id
            )
            return

        # Extract generated SQL
        sql_query = validation_result.get("sql_query", "")

        # Execute SQL query
        yield await format_sse_message(StreamEventType.SQL_EXECUTING, "Executing query...", session_id)

        success, results, error = await sql_query_service.execute_query(sql_query, user_id)

        if not success:
            yield await format_sse_message(
                StreamEventType.ERROR,
                f"Query execution failed: {error}",
                session_id
            )
            return

        # Format results using ResultFormatterAgent
        yield await format_sse_message(StreamEventType.PROCESSING, "Formatting results...", session_id)

        # Create context with query results
        results_context = f"Original Question: {user_question}\nSQL Query: {sql_query}\nQuery Results: {json.dumps(results)}"

        formatter_message = types.Content(
            role="user", parts=[types.Part.from_text(text=results_context)]
        )

        # Run formatter as standalone agent
        formatter_runner = Runner(
            app_name="agents",
            agent=sql_agent.result_formatter,
            session_service=session_service,
        )

        formatter_events = formatter_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=formatter_message,
        )

        formatted_answer = None
        async for event in formatter_events:
            if event.is_final_response() and event.content and event.content.parts:
                final_content = event.content.parts[0].text
                cleaned_response = re.sub(
                    r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                )
                try:
                    formatted_answer = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    formatted_answer = {"natural_language_answer": final_content}

        # Store assistant response
        answer_text = formatted_answer.get("natural_language_answer", "Query executed successfully") if formatted_answer else "Query executed successfully"

        assistant_message = ChatMessage(
            role="assistant",
            content=answer_text,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        await chat_history.store_message(assistant_message)

        # Send final response
        response_data = {
            "original_question": user_question,
            "generated_sql": sql_query,
            "query_results": results,
            "natural_language_answer": answer_text
        }

        yield await format_sse_message(
            StreamEventType.FINAL_RESPONSE,
            json.dumps(response_data),
            session_id,
            {"query_type": "sql_query"}
        )

    except Exception as e:
        yield await format_sse_message(StreamEventType.ERROR, f"SQL processing failed: {str(e)}", session_id)


async def stream_document_search_events(user_query: str, session_id: str, user_id: str):
    """Stream document search processing events in real-time"""
    try:
        # Get database session service from application state
        session_service: DatabaseSessionService = app.state.session_service

        # Store user message in chat history
        user_message = ChatMessage(
            role="user",
            content=user_query,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        await chat_history.store_message(user_message)
        await chat_history.update_session_timestamp(session_id)

        # Send initial status
        yield await format_sse_message(
            StreamEventType.STATUS,
            "Processing document search...",
            session_id
        )

        # Get or create ADK session
        current_session = None
        try:
            current_session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Session retrieval failed: {e}")

        if current_session is None:
            current_session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )

        # Step 1: Query Processing (Analyze + Retrieval Strategy)
        yield await format_sse_message(StreamEventType.DOC_ANALYZING, "Analyzing search query...", session_id)

        runner = Runner(
            app_name="agents",
            agent=document_agent.query_processing_agent,
            session_service=session_service,
        )

        user_message_adk = types.Content(
            role="user", parts=[types.Part.from_text(text=user_query)]
        )

        # Run query processing pipeline
        events = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message_adk,
        )

        retrieval_strategy = None
        async for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                final_content = event.content.parts[0].text
                cleaned_response = re.sub(
                    r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                )
                try:
                    retrieval_strategy = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    yield await format_sse_message(
                        StreamEventType.ERROR,
                        "Failed to parse query analysis result",
                        session_id
                    )
                    return

        if not retrieval_strategy:
            yield await format_sse_message(
                StreamEventType.ERROR,
                "Query analysis failed",
                session_id
            )
            return

        # Step 2: Retrieve documents from database using semantic search
        yield await format_sse_message(StreamEventType.DOC_RETRIEVING, "Retrieving relevant documents...", session_id)

        # Generate embedding for the query
        query_embedding = await embedding_service.generate_embedding(
            text=user_query,
            task_type="RETRIEVAL_QUERY"
        )

        # Use semantic search if embeddings are available, otherwise fall back to text search
        if query_embedding:
            retrieved_docs = await chat_history.search_documents_semantic(
                query_embedding=query_embedding,
                limit=retrieval_strategy.get("max_results", 10),
                threshold=0.3  # Lower threshold for better recall
            )
        else:
            # Fallback to text search if embeddings are not available
            search_terms = retrieval_strategy.get("search_terms", [])
            query_str = " ".join(search_terms) if search_terms else user_query
            retrieved_docs = await chat_history.search_documents_by_content(
                query=query_str,
                limit=retrieval_strategy.get("max_results", 10)
            )

        if not retrieved_docs:
            # No documents found - return empty result using clean_topic if available
            clean_topic = retrieval_strategy.get("clean_topic", user_query)
            answer_text = f"I couldn't find any documents about {clean_topic}. The knowledge base may not contain information about {clean_topic}."

            assistant_message = ChatMessage(
                role="assistant",
                content=answer_text,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now().isoformat()
            )
            await chat_history.store_message(assistant_message)

            response_data = {
                "original_query": user_query,
                "retrieved_documents": [],
                "answer": answer_text,
                "total_results": 0
            }

            yield await format_sse_message(
                StreamEventType.FINAL_RESPONSE,
                json.dumps(response_data),
                session_id,
                {"query_type": "document_search"}
            )
            return

        # Step 3: Rank and synthesize answer
        yield await format_sse_message(StreamEventType.DOC_RANKING, "Ranking documents...", session_id)

        # Prepare context for result processing
        docs_context = f"""Original Query: {user_query}
Query Analysis: {json.dumps(retrieval_strategy)}

Retrieved Documents:
{json.dumps(retrieved_docs, indent=2)}"""

        result_message = types.Content(
            role="user", parts=[types.Part.from_text(text=docs_context)]
        )

        # Run result processing pipeline (ranker + synthesizer)
        yield await format_sse_message(StreamEventType.DOC_SYNTHESIZING, "Synthesizing answer...", session_id)

        result_runner = Runner(
            app_name="agents",
            agent=document_agent.result_processing_agent,
            session_service=session_service,
        )

        result_events = result_runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=result_message,
        )

        final_answer = None
        async for event in result_events:
            if event.is_final_response() and event.content and event.content.parts:
                final_content = event.content.parts[0].text
                cleaned_response = re.sub(
                    r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                )
                try:
                    final_answer = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    final_answer = {"answer": final_content, "sources_used": [], "confidence": 0.5}

        # Store assistant response
        answer_text = final_answer.get("answer", "Document search completed") if final_answer else "Document search completed"

        assistant_message = ChatMessage(
            role="assistant",
            content=answer_text,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        await chat_history.store_message(assistant_message)

        # Format documents for response
        from models import SearchResultDocument
        formatted_docs = [
            SearchResultDocument(
                document_id=str(doc["document_id"]),
                title=doc["title"],
                file_type=doc.get("file_type"),
                metadata=doc.get("metadata"),
                snippet=doc.get("snippet", ""),
                relevance_score=None,  # Will be set by ranker in full implementation
                created_at=doc["created_at"]
            ).model_dump()
            for doc in retrieved_docs[:10]
        ]

        # Send final response
        response_data = {
            "original_query": user_query,
            "retrieved_documents": formatted_docs,
            "answer": answer_text,
            "total_results": len(retrieved_docs)
        }

        yield await format_sse_message(
            StreamEventType.FINAL_RESPONSE,
            json.dumps(response_data),
            session_id,
            {"query_type": "document_search"}
        )

    except Exception as e:
        yield await format_sse_message(StreamEventType.ERROR, f"Document search failed: {str(e)}", session_id)


async def stream_agent_events(customer_inquiry: str, session_id: str, user_id: str):
    """Stream agent processing events in real-time"""
    try:
        # Get database session service from application state
        session_service: DatabaseSessionService = app.state.session_service

        # Store user message in chat history
        user_message = ChatMessage(
            role="user",
            content=customer_inquiry,
            session_id=session_id,
            user_id=user_id,
            timestamp=datetime.now().isoformat()
        )
        await chat_history.store_message(user_message)

        # Update session timestamp
        await chat_history.update_session_timestamp(session_id)

        # Get conversation context for agent
        conversation_context = await chat_history.get_conversation_context(session_id, limit=10)

        # Send initial processing status with session info
        yield await format_sse_message(
            StreamEventType.STATUS,
            "Starting processing...",
            session_id,
            {"session_created": session_id, "has_context": bool(conversation_context)}
        )

        # Try to get existing session or create new one
        current_session = None
        try:
            current_session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Session retrieval failed for session_id='{session_id}': {e}")

        # If no session found, create new session
        if current_session is None:
            current_session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=session_id,
            )
            yield await format_sse_message(StreamEventType.STATUS, "Session created", session_id)
        else:
            yield await format_sse_message(StreamEventType.STATUS, "Session resumed", session_id)

        # Initialize the ADK Runner
        runner = Runner(
            app_name="agents",
            agent=customer_agent.root_agent,
            session_service=session_service,
        )

        # Format the user query with conversation context
        query_with_context = customer_inquiry
        if conversation_context:
            query_with_context = f"Previous conversation:\n{conversation_context}\n\nCurrent message: {customer_inquiry}"

        user_message = types.Content(
            role="user", parts=[types.Part.from_text(text=query_with_context)]
        )

        # Stream processing status
        yield await format_sse_message(StreamEventType.PROCESSING, "Analyzing inquiry...", session_id)

        # Run the agent and stream events
        events = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        )

        agent_step = "initializing"
        async for event in events:
            # Determine current processing step
            if hasattr(event, 'agent_name') or hasattr(event, 'content'):
                if "categorizer" in str(event).lower():
                    if agent_step != "categorizing":
                        agent_step = "categorizing"
                        yield await format_sse_message(StreamEventType.CATEGORIZING, "Categorizing inquiry...", session_id)
                elif "responder" in str(event).lower():
                    if agent_step != "responding":
                        agent_step = "responding"
                        yield await format_sse_message(StreamEventType.RESPONDING, "Generating response...", session_id)

            # Check for partial responses
            if event.content and event.content.parts:
                content = event.content.parts[0].text
                if content and not event.is_final_response():
                    yield await format_sse_message(StreamEventType.PARTIAL_RESPONSE, content, session_id)

            # Handle final response
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_content = event.content.parts[0].text

                    # Clean up response
                    cleaned_response = re.sub(
                        r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                    )

                    try:
                        response_data = json.loads(cleaned_response)

                        # Store assistant response in chat history
                        assistant_message = ChatMessage(
                            role="assistant",
                            content=response_data.get("suggested_response", ""),
                            session_id=session_id,
                            user_id=user_id,
                            timestamp=datetime.now().isoformat()
                        )
                        await chat_history.store_message(assistant_message)

                        yield await format_sse_message(
                            StreamEventType.FINAL_RESPONSE,
                            json.dumps(response_data),
                            session_id,
                            {"original_inquiry": customer_inquiry}
                        )
                    except json.JSONDecodeError:
                        yield await format_sse_message(
                            StreamEventType.ERROR,
                            "Failed to parse agent response",
                            session_id
                        )

    except Exception as e:
        yield await format_sse_message(StreamEventType.ERROR, f"Processing failed: {str(e)}", session_id)


async def stream_with_routing(user_message: str, session_id: str, user_id: str):
    """Route queries to SQL or customer service pipeline based on classification"""
    try:
        # Get database session service
        session_service: DatabaseSessionService = app.state.session_service

        # Send routing status
        yield await format_sse_message(
            StreamEventType.SQL_ROUTING,
            "Classifying query...",
            session_id
        )

        # Create or get router session
        # Note: Using "agents" as app_name because RouterLlmAgent is imported from google.adk.agents
        # Use consistent session ID to maintain conversation history for better routing decisions
        router_session_id = f"{session_id}-router"
        router_session = None
        try:
            router_session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=router_session_id,
            )
        except Exception as e:
            print(f"Router session retrieval failed for session_id='{router_session_id}': {e}")

        # If no session found, create new session
        if router_session is None:
            router_session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=router_session_id,
            )

        # Run RouterAgent using ADK framework
        # Using "agents" app_name to match the inferred app_name from LlmAgent's package location
        router_runner = Runner(
            app_name="agents",
            agent=router_agent.root_agent,
            session_service=session_service
        )

        router_message = types.Content(
            role="user", parts=[types.Part.from_text(text=user_message)]
        )

        router_events = router_runner.run_async(
            user_id=user_id,
            session_id=router_session_id,
            new_message=router_message,
        )

        routing_decision = None
        async for event in router_events:
            if event.is_final_response() and event.content and event.content.parts:
                final_content = event.content.parts[0].text
                cleaned_response = re.sub(
                    r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                )
                try:
                    routing_decision = json.loads(cleaned_response)
                except json.JSONDecodeError:
                    routing_decision = {"query_type": "customer_service"}

        # Route based on classification
        query_type = routing_decision.get("query_type", "customer_service") if routing_decision else "customer_service"

        if query_type == "sql_query":
            yield await format_sse_message(
                StreamEventType.STATUS,
                "Routing to SQL pipeline...",
                session_id,
                {"route": "sql_query"}
            )
            # Stream SQL query events
            async for event in stream_sql_query_events(user_message, session_id, user_id):
                yield event
        elif query_type == "document_search":
            yield await format_sse_message(
                StreamEventType.STATUS,
                "Routing to document search...",
                session_id,
                {"route": "document_search"}
            )
            # Stream document search events
            async for event in stream_document_search_events(user_message, session_id, user_id):
                yield event
        elif query_type == "customer_service":
            yield await format_sse_message(
                StreamEventType.STATUS,
                "Routing to customer service...",
                session_id,
                {"route": "customer_service"}
            )
            # Stream customer service events
            async for event in stream_agent_events(user_message, session_id, user_id):
                yield event
        elif query_type == "clarification_needed":
            # Query is ambiguous, ask for clarification
            clarification_question = routing_decision.get("clarification_question", "Could you please provide more details about your request?")

            yield await format_sse_message(
                StreamEventType.STATUS,
                "Requesting clarification...",
                session_id,
                {"route": "clarification_needed"}
            )

            # Store user message
            user_msg = ChatMessage(
                role="user",
                content=user_message,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now()
            )
            await chat_history.save_message(user_msg)

            # Store clarification response
            clarification_response = ChatMessage(
                role="assistant",
                content=clarification_question,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now()
            )
            await chat_history.save_message(clarification_response)

            # Send final clarification response
            yield await format_sse_message(
                StreamEventType.FINAL_RESPONSE,
                json.dumps({
                    "query_type": "clarification_needed",
                    "original_message": user_message,
                    "clarification_question": clarification_question,
                    "reasoning": routing_decision.get("reasoning", "Query requires clarification"),
                    "confidence": routing_decision.get("confidence", "low")
                }),
                session_id
            )
        else:
            # Unsupported query type
            yield await format_sse_message(
                StreamEventType.STATUS,
                "Query type not supported",
                session_id,
                {"route": "unsupported"}
            )

            # Store user message
            user_msg = ChatMessage(
                role="user",
                content=user_message,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now().isoformat()
            )
            await chat_history.store_message(user_msg)

            # Create error response
            error_message = "I'm sorry, but I can only handle SQL queries, document search queries, and customer service inquiries. Your query doesn't fit into any of these categories."

            # Store assistant response
            assistant_msg = ChatMessage(
                role="assistant",
                content=error_message,
                session_id=session_id,
                user_id=user_id,
                timestamp=datetime.now().isoformat()
            )
            await chat_history.store_message(assistant_msg)

            # Send final error response
            yield await format_sse_message(
                StreamEventType.FINAL_RESPONSE,
                json.dumps({
                    "error": "unsupported_query_type",
                    "message": error_message,
                    "supported_types": ["sql_query", "document_search", "customer_service"],
                    "received_type": query_type
                }),
                session_id,
                {"query_type": query_type}
            )

    except Exception as e:
        yield await format_sse_message(StreamEventType.ERROR, f"Routing failed: {str(e)}", session_id)


@router.post("/create-session", response_model=SessionResponse)
@limiter.limit("10/minute")
async def create_session(request: Request, session_data: SessionCreate):
    """
    Create a new chat session and return the session details.
    Use this session ID for subsequent stream-chat calls.
    """
    session_id = str(uuid.uuid4())

    # Create session in database
    session = await chat_history.create_session(
        session_id=session_id,
        user_id=session_data.user_id,
        title=session_data.title or "New Chat"
    )

    return SessionResponse(
        session_id=session["session_id"],
        user_id=session["user_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        message_count=0
    )


@router.get("/chat-history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str, limit: int = 50):
    """
    Retrieve chat history for a specific session.
    """
    messages = await chat_history.get_session_history(session_id, limit)
    total_count = await chat_history.get_session_count(session_id)

    return ChatHistoryResponse(
        session_id=session_id,
        messages=messages,
        total_count=total_count
    )


@router.post("/stream-chat")
@limiter.limit("10/minute")
async def stream_chat(request: Request, request_body: StreamingChatRequest):
    """
    Streaming endpoint for real-time chat with the multi-agent system.
    Automatically routes queries to SQL or customer service pipeline.
    Returns Server-Sent Events (SSE) stream.
    """
    # Generate session ID if not provided
    session_id = request_body.session_id or str(uuid.uuid4())
    user_id = request_body.user_id

    # Check if session exists, if not create it
    session_exists = await chat_history.session_exists(session_id)
    if not session_exists:
        await chat_history.create_session(
            session_id=session_id,
            user_id=user_id,
            title="New Chat"
        )

    # Auto-generate title from first message if session is new
    async def stream_with_title_generation():
        message_count = await chat_history.get_session_count(session_id)

        # Stream all agent events with automatic routing
        async for event in stream_with_routing(request_body.message, session_id, user_id):
            yield event

        # After first user message, auto-generate title
        if message_count == 0:
            await chat_history.auto_generate_title(session_id)

    return StreamingResponse(
        stream_with_title_generation(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )


@router.post("/process-inquiry", response_model=UnifiedInquiryResponse)
async def process_inquiry_unified(request_body: UnifiedInquiryRequest):
    """
    Unified endpoint with intelligent routing to SQL, document search, or customer service.
    Supports all features from SSE endpoint but returns immediate response without streaming.

    Request body:
    {
        "message": "Your query here",
        "user_id": "optional-user-id",
        "session_id": "optional-session-id"
    }

    Response includes query_type and type-specific response_data:
    - SQL: {original_question, generated_sql, query_results, natural_language_answer}
    - Document Search: {original_query, retrieved_documents, answer, total_results}
    - Customer Service: {original_inquiry, category, suggested_response}
    """
    # Extract message and optional parameters
    user_message = request_body.message
    user_id = request_body.user_id or str(uuid.uuid4())
    session_id = request_body.session_id or str(uuid.uuid4())

    try:
        # Get database session service
        session_service: DatabaseSessionService = app.state.session_service

        # Generate unique session IDs for each pipeline
        router_session_id = f"{session_id}-router"
        sql_session_id = f"{session_id}-sql"
        doc_session_id = f"{session_id}-doc"
        cs_session_id = f"{session_id}-cs"

        # Create or get router session
        # Note: Using "agents" as app_name because RouterLlmAgent is imported from google.adk.agents
        router_session = None
        try:
            router_session = await session_service.get_session(
                app_name="agents",
                user_id=user_id,
                session_id=router_session_id,
            )
        except Exception:
            pass

        # If no session found, create new session
        if router_session is None:
            router_session = await session_service.create_session(
                app_name="agents",
                user_id=user_id,
                session_id=router_session_id,
            )

        # Step 1: Route the query using router agent
        router_runner = Runner(
            app_name="agents",
            agent=router_agent.root_agent,
            session_service=session_service,
        )

        router_message = types.Content(
            role="user", parts=[types.Part.from_text(text=user_message)]
        )

        router_events = router_runner.run_async(
            user_id=user_id,
            session_id=router_session_id,
            new_message=router_message,
        )

        routing_result = None
        async for event in router_events:
            if event.is_final_response() and event.content and event.content.parts:
                routing_result = event.content.parts[0].text
                break

        if not routing_result:
            raise HTTPException(status_code=500, detail="Routing classification failed")

        # Parse routing decision
        cleaned_routing = re.sub(r"^```(?:json)?\n|```$", "", routing_result.strip(), flags=re.IGNORECASE)
        routing_data = json.loads(cleaned_routing)
        query_type = routing_data.get("query_type", "customer_service")

        # Step 2: Route to appropriate pipeline based on classification
        response_data = {}

        if query_type == "sql_query":
            # SQL Query Pipeline
            # Create or get SQL session
            sql_current_session = None
            try:
                sql_current_session = await session_service.get_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=sql_session_id,
                )
            except Exception:
                pass

            if sql_current_session is None:
                sql_current_session = await session_service.create_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=sql_session_id,
                )

            # Step 1: SQL Generation (schema, generation, validation)
            sql_runner = Runner(
                app_name="agents",
                agent=sql_agent.sql_generation_agent,
                session_service=session_service,
            )

            sql_message = types.Content(
                role="user", parts=[types.Part.from_text(text=user_message)]
            )

            sql_events = sql_runner.run_async(
                user_id=user_id,
                session_id=sql_session_id,
                new_message=sql_message,
            )

            validation_result = None
            async for event in sql_events:
                if event.is_final_response() and event.content and event.content.parts:
                    final_content = event.content.parts[0].text
                    cleaned_response = re.sub(
                        r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                    )
                    try:
                        validation_result = json.loads(cleaned_response)
                    except json.JSONDecodeError:
                        pass
                    break

            # SqlGeneratorAgent returns {"sql_query": "...", "explanation": "..."}
            if not validation_result or not validation_result.get("sql_query"):
                error_msg = "Failed to generate SQL query"
                response_data = {
                    "original_question": user_message,
                    "generated_sql": None,
                    "query_results": None,
                    "natural_language_answer": f"SQL generation failed: {error_msg}",
                    "error": error_msg
                }
            else:
                # Step 2: Execute SQL query
                sql_query = validation_result.get("sql_query", "")
                success, results, error = await sql_query_service.execute_query(sql_query, user_id)

                if not success:
                    response_data = {
                        "original_question": user_message,
                        "generated_sql": sql_query,
                        "query_results": None,
                        "natural_language_answer": f"Query execution failed: {error}",
                        "error": error
                    }
                else:
                    # Step 3: Format results using ResultFormatterAgent
                    results_context = f"Original Question: {user_message}\nSQL Query: {sql_query}\nQuery Results: {json.dumps(results)}"

                    formatter_message = types.Content(
                        role="user", parts=[types.Part.from_text(text=results_context)]
                    )

                    formatter_runner = Runner(
                        app_name="agents",
                        agent=sql_agent.result_formatter,
                        session_service=session_service,
                    )

                    formatter_events = formatter_runner.run_async(
                        user_id=user_id,
                        session_id=sql_session_id,
                        new_message=formatter_message,
                    )

                    formatted_answer = None
                    async for event in formatter_events:
                        if event.is_final_response() and event.content and event.content.parts:
                            final_content = event.content.parts[0].text
                            cleaned_response = re.sub(
                                r"^```(?:json)?\n|```$", "", final_content.strip(), flags=re.IGNORECASE
                            )
                            try:
                                formatted_answer = json.loads(cleaned_response)
                            except json.JSONDecodeError:
                                formatted_answer = {"natural_language_answer": final_content}
                            break

                    answer_text = formatted_answer.get("natural_language_answer", "Query executed successfully") if formatted_answer else "Query executed successfully"

                    response_data = {
                        "original_question": user_message,
                        "generated_sql": sql_query,
                        "query_results": results,
                        "natural_language_answer": answer_text,
                        "error": None
                    }

        elif query_type == "document_search":
            # Document Search Pipeline
            # Create or get session (use single session for entire document search pipeline)
            doc_current_session = None
            try:
                doc_current_session = await session_service.get_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=doc_session_id,
                )
            except Exception:
                pass

            if doc_current_session is None:
                doc_current_session = await session_service.create_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=doc_session_id,
                )

            # Check if this is a confirmation response to a previous query rewrite
            recent_history = await chat_history.get_session_history(session_id, limit=5)
            pending_rewrite = None

            # Look for the most recent query_confirmation in history
            for msg in reversed(recent_history):
                if msg.role == "assistant" and "Did you mean:" in msg.content:
                    # Extract the rewritten query from the confirmation message
                    import re as re_module
                    match = re_module.search(r"Did you mean: '([^']+)'\?", msg.content)
                    if match:
                        pending_rewrite = match.group(1)
                        break

            # Check if user is confirming the rewrite
            user_response_lower = user_message.lower().strip()
            if pending_rewrite and user_response_lower in ["yes", "confirm", "yes, search for that", "y"]:
                # User confirmed - use the rewritten query instead
                user_message = pending_rewrite
                print(f"✅ User confirmed rewrite. Using: '{user_message}'")
            elif pending_rewrite and user_response_lower in ["no", "edit", "no, let me rephrase"]:
                # User wants to rephrase - ask them to provide a new query
                return UnifiedInquiryResponse(
                    query_type="clarification_needed",
                    original_message=user_message,
                    response_data={
                        "clarification_question": "Please rephrase your search query:",
                        "reasoning": "User requested to rephrase the query",
                        "confidence": "high",
                        "original_query": user_message
                    },
                    session_id=session_id
                )
            elif pending_rewrite and "original" in user_response_lower:
                # User wants to search with original - extract it from history
                for msg in reversed(recent_history):
                    if msg.role == "user" and msg.content not in ["yes", "no", "confirm", "edit", "original"]:
                        user_message = msg.content
                        print(f"🔄 User requested original query. Using: '{user_message}'")
                        break

            # Step 2a: Query Processing (Analyze + Retrieval Strategy)
            query_runner = Runner(
                app_name="agents",
                agent=document_agent.query_processing_agent,
                session_service=session_service,
            )

            query_message = types.Content(
                role="user", parts=[types.Part.from_text(text=user_message)]
            )

            query_events = query_runner.run_async(
                user_id=user_id,
                session_id=doc_session_id,
                new_message=query_message,
            )

            query_analysis = None
            async for event in query_events:
                if event.is_final_response() and event.content and event.content.parts:
                    query_analysis = event.content.parts[0].text
                    break

            if not query_analysis:
                response_data = {"error": "Document query analysis failed"}
            else:
                cleaned_analysis = re.sub(r"^```(?:json)?\n|```$", "", query_analysis.strip(), flags=re.IGNORECASE)
                analysis_data = json.loads(cleaned_analysis)

                # Check if query needs confirmation due to rewriting
                if analysis_data.get("needs_confirmation", False):
                    confirmation_msg = f"I noticed your query might have a grammatical issue. Did you mean: '{analysis_data.get('rewritten_query')}'?"

                    # Ensure session exists in chat history
                    session_exists = await chat_history.session_exists(session_id)
                    if not session_exists:
                        await chat_history.create_session(
                            session_id=session_id,
                            user_id=user_id,
                            title="New Search"
                        )

                    # Save user message and confirmation to chat history
                    user_msg = ChatMessage(
                        role="user",
                        content=user_message,
                        session_id=session_id,
                        user_id=user_id,
                        timestamp=datetime.now().isoformat()
                    )
                    await chat_history.store_message(user_msg)

                    assistant_msg = ChatMessage(
                        role="assistant",
                        content=confirmation_msg,
                        session_id=session_id,
                        user_id=user_id,
                        timestamp=datetime.now().isoformat()
                    )
                    await chat_history.store_message(assistant_msg)

                    return UnifiedInquiryResponse(
                        query_type="query_confirmation",
                        original_message=user_message,
                        response_data={
                            "original_query": analysis_data.get("original_query", user_message),
                            "rewritten_query": analysis_data.get("rewritten_query"),
                            "rewrite_reason": analysis_data.get("rewrite_reason"),
                            "confirmation_message": confirmation_msg,
                            "suggested_actions": [
                                {"action": "confirm", "label": "Yes, search for that"},
                                {"action": "edit", "label": "No, let me rephrase"},
                                {"action": "original", "label": "No, search as-is"}
                            ]
                        },
                        session_id=session_id
                    )

                # Extract search parameters
                search_terms = analysis_data.get("keywords", []) + analysis_data.get("expanded_terms", [])
                query_str = " ".join(search_terms) if search_terms else user_message

                # Step 2b: Retrieve documents from database
                retrieved_docs = await chat_history.search_documents_by_content(
                    query=query_str,
                    limit=10
                )

                if not retrieved_docs:
                    # No documents found - use clean_topic from analysis
                    clean_topic = analysis_data.get("clean_topic", user_message)
                    response_data = {
                        "original_query": user_message,
                        "retrieved_documents": [],
                        "answer": f"I couldn't find any documents about {clean_topic}. The knowledge base may not contain information about {clean_topic}.",
                        "total_results": 0
                    }
                else:
                    # Step 2c: Rank and synthesize answer
                    result_runner = Runner(
                        app_name="agents",
                        agent=document_agent.result_processing_agent,
                        session_service=session_service,
                    )

                    # Prepare context for result processing (matching SSE endpoint format)
                    docs_context = f"""Original Query: {user_message}
Query Analysis: {json.dumps(analysis_data)}

Retrieved Documents:
{json.dumps(retrieved_docs, indent=2)}"""

                    result_message = types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=docs_context)]
                    )

                    result_events = result_runner.run_async(
                        user_id=user_id,
                        session_id=doc_session_id,
                        new_message=result_message,
                    )

                    final_result = None
                    async for event in result_events:
                        if event.is_final_response() and event.content and event.content.parts:
                            final_result = event.content.parts[0].text
                            break

                    if final_result:
                        cleaned_result = re.sub(r"^```(?:json)?\n|```$", "", final_result.strip(), flags=re.IGNORECASE)
                        try:
                            answer_data = json.loads(cleaned_result)
                            answer_text = answer_data.get("answer", "Document search completed")
                        except json.JSONDecodeError:
                            answer_text = final_result
                    else:
                        answer_text = "No answer could be generated"

                    # Format response to match DocumentSearchResponse structure
                    from models import SearchResultDocument
                    formatted_docs = [
                        SearchResultDocument(
                            document_id=str(doc["document_id"]),
                            title=doc["title"],
                            file_type=doc.get("file_type"),
                            metadata=doc.get("metadata"),
                            snippet=doc.get("snippet", doc.get("content", "")[:200]),
                            relevance_score=None,
                            created_at=doc["created_at"]
                        ).model_dump()
                        for doc in retrieved_docs[:10]
                    ]

                    response_data = {
                        "original_query": user_message,
                        "retrieved_documents": formatted_docs,
                        "answer": answer_text,
                        "total_results": len(retrieved_docs)
                    }

        elif query_type == "customer_service":
            # Customer Service Pipeline
            # Create or get CS session
            cs_session = None
            try:
                cs_session = await session_service.get_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=cs_session_id,
                )
            except Exception:
                pass

            if cs_session is None:
                cs_session = await session_service.create_session(
                    app_name="agents",
                    user_id=user_id,
                    session_id=cs_session_id,
                )

            cs_runner = Runner(
                app_name="agents",
                agent=customer_agent.root_agent,
                session_service=session_service,
            )

            cs_message = types.Content(
                role="user", parts=[types.Part.from_text(text=user_message)]
            )

            cs_events = cs_runner.run_async(
                user_id=user_id,
                session_id=cs_session_id,
                new_message=cs_message,
            )

            cs_result = None
            async for event in cs_events:
                if event.is_final_response() and event.content and event.content.parts:
                    cs_result = event.content.parts[0].text
                    break

            if cs_result:
                cleaned_cs = re.sub(r"^```(?:json)?\n|```$", "", cs_result.strip(), flags=re.IGNORECASE)
                response_data = json.loads(cleaned_cs)
            else:
                response_data = {"error": "Customer service processing failed"}

        elif query_type == "clarification_needed":
            # Query is ambiguous, ask for clarification
            clarification_question = routing_data.get("clarification_question", "Could you please provide more details about your request?")

            response_data = {
                "clarification_question": clarification_question,
                "reasoning": routing_data.get("reasoning", "Query requires clarification"),
                "confidence": routing_data.get("confidence", "low"),
                "original_query": user_message
            }

        else:
            # Unsupported query type
            response_data = {
                "error": "unsupported_query_type",
                "message": "I'm sorry, but I can only handle SQL queries, document search queries, and customer service inquiries. Your query doesn't fit into any of these categories.",
                "supported_types": ["sql_query", "document_search", "customer_service"],
                "received_type": query_type
            }

        # Return unified response
        return UnifiedInquiryResponse(
            query_type=query_type,
            original_message=user_message,
            response_data=response_data,
            session_id=session_id
        )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse agent response: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process inquiry: {e}")


@router.get("/sessions", response_model=SessionListResponse)
async def get_user_sessions(user_id: str):
    """
    Get all chat sessions for a specific user, ordered by most recently updated.
    """
    sessions_data = await chat_history.get_user_sessions(user_id)

    sessions = [
        SessionResponse(
            session_id=s["session_id"],
            user_id=s["user_id"],
            title=s["title"],
            created_at=s["created_at"],
            updated_at=s["updated_at"],
            message_count=s["message_count"]
        )
        for s in sessions_data
    ]

    return SessionListResponse(
        sessions=sessions,
        total_count=len(sessions)
    )


@router.patch("/sessions/{session_id}/title")
async def update_session_title(session_id: str, request_body: UpdateTitleRequest):
    """
    Update the title of a specific session.
    """
    success = await chat_history.update_session_title(session_id, request_body.title)

    if not success:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "title": request_body.title,
        "updated": True
    }


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str):
    """
    Delete a session and all its messages.
    """
    result = await chat_history.delete_session(session_id)

    if not result["deleted"]:
        raise HTTPException(status_code=404, detail="Session not found")

    return DeleteSessionResponse(
        session_id=result["session_id"],
        deleted=result["deleted"],
        messages_deleted=result["messages_deleted"]
    )


@router.post("/messages/{message_id}/feedback")
async def update_message_feedback(message_id: str, request_body: MessageFeedbackRequest):
    """
    Update feedback (like/dislike) for a specific message.
    Supports toggle behavior: click like when liked removes like, click dislike when liked sets dislike.
    """
    success = await chat_history.update_message_feedback(message_id, request_body.feedback)

    if not success:
        raise HTTPException(status_code=404, detail="Message not found")

    return {
        "message_id": message_id,
        "feedback": request_body.feedback,
        "updated": True
    }


# ======================================
# Document Management Endpoints
# ======================================

@router.post("/documents", response_model=DocumentResponse)
async def upload_document(request_body: DocumentUploadRequest):
    """
    Upload a new document to the knowledge base with semantic embeddings.
    Automatically generates embeddings for semantic search.
    """
    from models import DocumentUploadRequest
    import uuid

    document_id = str(uuid.uuid4())

    # Generate embedding for the document content
    embedding = await embedding_service.generate_embedding(
        text=request_body.content,
        task_type="RETRIEVAL_DOCUMENT"
    )

    # Store document in database with embedding
    result = await chat_history.store_document(
        document_id=document_id,
        title=request_body.title,
        content=request_body.content,
        file_type=request_body.file_type,
        metadata=request_body.metadata,
        embedding=embedding
    )

    return DocumentResponse(
        document_id=document_id,
        title=request_body.title,
        file_type=request_body.file_type,
        metadata=request_body.metadata,
        content_length=len(request_body.content),
        created_at=result.get("created_at", datetime.now().isoformat())
    )


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(limit: int = 50, offset: int = 0):
    """
    Get list of all documents in the knowledge base.
    """
    result = await chat_history.get_all_documents(limit=limit, offset=offset)

    document_responses = [
        DocumentResponse(
            document_id=str(doc["document_id"]),
            title=doc["title"],
            file_type=doc.get("file_type"),
            metadata=doc.get("metadata"),
            content_length=doc.get("content_length", 0),
            created_at=doc["created_at"],
            updated_at=doc.get("updated_at")
        )
        for doc in result["documents"]
    ]

    return DocumentListResponse(
        documents=document_responses,
        total_count=result["total_count"],
        limit=limit,
        offset=offset
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: str):
    """
    Get a specific document by ID with full content.
    """
    document = await chat_history.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetailResponse(
        document_id=str(document["document_id"]),
        title=document["title"],
        content=document["content"],
        file_type=document.get("file_type"),
        metadata=document.get("metadata"),
        created_at=document["created_at"],
        updated_at=document.get("updated_at")
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document from the knowledge base.
    """
    success = await chat_history.delete_document(document_id)

    if not success:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": document_id,
        "deleted": True
    }


# Include the router in the FastAPI app
app.include_router(router, prefix="/api", tags=["Customer Inquiry Processing"])

# Root endpoint
@app.get("/")
async def read_root():
    return {
        "message": "Customer Inquiry Processor API",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "sessions": "/api/sessions?user_id={user_id}",
            "create_session": "/api/create-session",
            "stream_chat": "/api/stream-chat",
            "chat_history": "/api/chat-history/{session_id}",
            "update_title": "/api/sessions/{session_id}/title",
            "delete_session": "/api/sessions/{session_id}",
            "message_feedback": "/api/messages/{message_id}/feedback"
        }
    }
