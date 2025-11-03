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
    UpdateTitleRequest, MessageFeedbackRequest, DeleteSessionResponse
)
import asyncio
from datetime import datetime, timedelta
from chat_history_postgres import ChatHistoryServicePostgres
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from agents.customer_agent import CustomerAgentOrchestrator
from agents.sql_agent import SqlAgentOrchestrator
from agents.router import RouterOrchestrator
from sql_query_service import SqlQueryService
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
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Session retrieval failed: {e}")

        if current_session is None:
            current_session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

        # Initialize SQL Generation Runner
        yield await format_sse_message(StreamEventType.SQL_GENERATING, "Generating SQL query...", session_id)

        runner = Runner(
            app_name=APP_NAME,
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
                except json.JSONDecodeError:
                    yield await format_sse_message(
                        StreamEventType.ERROR,
                        "Failed to parse SQL validation result",
                        session_id
                    )
                    return

        if not validation_result or not validation_result.get("is_valid"):
            error_msg = validation_result.get("issues", ["SQL query validation failed"]) if validation_result else ["Unknown error"]
            yield await format_sse_message(
                StreamEventType.ERROR,
                f"SQL validation failed: {', '.join(error_msg)}",
                session_id
            )
            return

        # Extract validated SQL
        sql_query = validation_result.get("validated_sql", "")

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
            app_name=APP_NAME,
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
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(f"Session retrieval failed for session_id='{session_id}': {e}")

        # If no session found, create new session
        if current_session is None:
            current_session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
            yield await format_sse_message(StreamEventType.STATUS, "Session created", session_id)
        else:
            yield await format_sse_message(StreamEventType.STATUS, "Session resumed", session_id)

        # Initialize the ADK Runner
        runner = Runner(
            app_name=APP_NAME,
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
        router_session_id = f"{session_id}-router-{hash(user_message) % 10000}"
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
        else:
            yield await format_sse_message(
                StreamEventType.STATUS,
                "Routing to customer service...",
                session_id,
                {"route": "customer_service"}
            )
            # Stream customer service events
            async for event in stream_agent_events(user_message, session_id, user_id):
                yield event

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


@router.post("/process-inquiry", response_model=CustomerInquiryResponse)
async def process_customer_inquiry(request_body: CustomerInquiryRequest):
    """
    Endpoint to interact with the multi-agent ADK system.
    request_body: {"customer_inquiry": "My internet is not working after the update, please help!"}
    """
    # Extract customer inquiry from request
    customer_inquiry = request_body.customer_inquiry

    # Generate unique IDs for this processing session
    unique_id = str(uuid.uuid4())
    session_id = unique_id
    user_id = unique_id

    try:
        # Get database session service from application state
        session_service: DatabaseSessionService = app.state.session_service

        # Try to get existing session or create new one
        current_session = None
        try:
            current_session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
        except Exception as e:
            print(
                f"Existing Session retrieval failed for session_id='{session_id}' "
                f"and user_uid='{user_id}': {e}"
            )

        # If no session found, creating new session
        if current_session is None:
            current_session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )
        else:
            print(f"Existing session '{session_id}'has been found. Resuming session.")

        # Initialize the ADK Runner with our multi-agent pipeline
        runner = Runner(
            app_name=APP_NAME,
            agent=customer_agent.root_agent,
            session_service=session_service,
        )

        # Format the user query as a structured message using the google genais content types
        user_message = types.Content(
            role="user", parts=[types.Part.from_text(text=customer_inquiry)]
        )

        # Run the agent asynchronously
        events = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        )

        # Process events to find the final response
        final_response = None
        last_event_content = None
        async for event in events:
            if event.is_final_response():
                if event.content and event.content.parts:
                    last_event_content = event.content.parts[0].text

        if last_event_content:
            final_response = last_event_content
        else:
            print("No final response event found from the Sequential Agent.")

        # Parse the JSON response from agents
        if final_response is None:
            raise HTTPException(status_code=500, detail="No response received from agent.")

        # Clean up Markdown code block if it exists
        # This handles responses like: ```json\n{ ... }\n```
        cleaned_response = re.sub(
            r"^```(?:json)?\n|```$", "", final_response.strip(), flags=re.IGNORECASE
        )

        # Loading the cleaned JSON
        try:
            response_data = json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Agent response is not valid JSON.")

        # Return the structured response using your Pydantic model
        return CustomerInquiryResponse(
            original_inquiry=response_data.get("original_inquiry", ""),
            category=response_data.get("category", ""),
            suggested_response=response_data.get("suggested_response", ""),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process agent query: {e}")


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
