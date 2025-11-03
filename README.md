# Customer Inquiry Chat API

A production-ready FastAPI-based chat application with PostgreSQL backend, SSE streaming, session management, and user feedback capabilities.

## 🚀 Features

- **SSE Streaming**: Real-time Server-Sent Events for chat responses
- **Text-to-SQL Queries**: Natural language to SQL conversion with intelligent routing
- **Document Search & Retrieval**: Semantic search over knowledge base with multi-agent processing
- **PostgreSQL Database**: Robust storage with session and message management
- **Session Management**: Create, list, update, and delete chat sessions
- **User Feedback**: Like/dislike toggle for individual messages
- **Auto-generated Titles**: Session titles auto-generated from first message
- **Multi-agent Processing**: Google ADK integration for intelligent response categorization
- **Intelligent Routing**: Automatic 3-way classification between SQL queries, document search, and customer service
- **Rate Limiting**: Built-in protection against API abuse
- **No Authentication Required**: Simple anonymous user tracking via user_id

## 📋 Requirements

- Python 3.8+
- PostgreSQL 16+
- Google Cloud credentials (for Vertex AI)

## 🛠️ Setup

### 1. Clone and Install Dependencies

```bash
cd /path/to/agents_app
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file:

```bash
# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT="your-project-id"
GOOGLE_CLOUD_LOCATION="us-central1"
GOOGLE_GENAI_USE_VERTEXAI=TRUE

# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chat_history

# SQL Query Configuration (Optional)
SQL_ALLOWED_TABLES=orders
SQL_MAX_RESULTS=100
```

### 3. Authenticate with Google Cloud

```bash
gcloud auth application-default login
gcloud config set project your-project-id
```

### 4. Create PostgreSQL Database

```bash
createdb chat_history
# Or using PostgreSQL: CREATE DATABASE chat_history;
```

### 5. Run the Application

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will auto-create database tables on first request.

## 📚 API Endpoints

### Session Management

#### Create Session
```bash
POST /api/create-session
Content-Type: application/json

{
  "user_id": "user-123",
  "title": "My Chat Session"  # Optional, defaults to "New Chat"
}

Response:
{
  "session_id": "uuid",
  "user_id": "user-123",
  "title": "My Chat Session",
  "created_at": "2025-11-02T12:00:00",
  "updated_at": "2025-11-02T12:00:00",
  "message_count": 0
}
```

#### List User Sessions
```bash
GET /api/sessions?user_id={user_id}

Response:
{
  "sessions": [
    {
      "session_id": "uuid",
      "user_id": "user-123",
      "title": "My Chat Session",
      "message_count": 5,
      "created_at": "2025-11-02T12:00:00",
      "updated_at": "2025-11-02T12:05:00"
    }
  ],
  "total_count": 1
}
```

#### Update Session Title
```bash
PATCH /api/sessions/{session_id}/title
Content-Type: application/json

{
  "title": "New Title"
}

Response:
{
  "session_id": "uuid",
  "title": "New Title",
  "updated": true
}
```

#### Delete Session
```bash
DELETE /api/sessions/{session_id}

Response:
{
  "session_id": "uuid",
  "deleted": true,
  "messages_deleted": 5
}
```

### Chat & Messaging

#### Stream Chat (SSE)
```bash
POST /api/stream-chat
Content-Type: application/json

{
  "message": "My internet is not working",
  "user_id": "user-123",
  "session_id": "uuid"  # Optional, creates new if not provided
}

Response: Server-Sent Events stream
data: {"event_type":"status","data":"Starting processing...","session_id":"uuid","timestamp":"2025-11-02T12:00:00"}

data: {"event_type":"categorizing","data":"Categorizing inquiry...","session_id":"uuid","timestamp":"2025-11-02T12:00:01"}

data: {"event_type":"responding","data":"Generating response...","session_id":"uuid","timestamp":"2025-11-02T12:00:02"}

data: {"event_type":"final_response","data":"{\"original_inquiry\":\"...\",\"category\":\"Technical Support\",\"suggested_response\":\"...\"}","session_id":"uuid","timestamp":"2025-11-02T12:00:03"}
```

**Event Types:**
- `status`: Processing stage updates
- `sql_routing`: Classifying query for routing
- `sql_generating`: Generating SQL query
- `sql_validating`: Validating SQL query
- `sql_executing`: Executing SQL query
- `doc_analyzing`: Analyzing document search query
- `doc_retrieving`: Retrieving relevant documents
- `doc_ranking`: Ranking documents by relevance
- `doc_synthesizing`: Synthesizing answer from documents
- `processing`: Analyzing inquiry or formatting results
- `categorizing`: Categorizing customer service inquiry
- `responding`: Generating customer service response
- `final_response`: Complete structured response (SQL, document search, or customer service)
- `error`: Error occurred

**Note**: On first message to a new session, the title will be auto-generated from the first 50 characters.

#### Get Chat History
```bash
GET /api/chat-history/{session_id}?limit=50

Response:
{
  "session_id": "uuid",
  "messages": [
    {
      "message_id": "msg-uuid",
      "session_id": "uuid",
      "user_id": "user-123",
      "role": "user",
      "content": "My internet is not working",
      "feedback": null,
      "timestamp": "2025-11-02T12:00:00"
    },
    {
      "message_id": "msg-uuid-2",
      "session_id": "uuid",
      "user_id": "user-123",
      "role": "assistant",
      "content": "Thank you for contacting technical support...",
      "feedback": "like",
      "timestamp": "2025-11-02T12:00:03"
    }
  ],
  "total_count": 2
}
```

### Text-to-SQL Queries

The application automatically routes queries between SQL data retrieval and customer service responses.

#### SQL Query Flow

```bash
POST /api/stream-chat
Content-Type: application/json

{
  "message": "How many orders do I have?",
  "user_id": "test-user-123",
  "session_id": "uuid"
}

Response: Server-Sent Events stream
data: {"event_type":"sql_routing","data":"Classifying query...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"status","data":"Routing to SQL pipeline...","session_id":"uuid","metadata":{"route":"sql_query"}}

data: {"event_type":"sql_generating","data":"Generating SQL query...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"sql_executing","data":"Executing query...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"processing","data":"Formatting results...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"final_response","data":"{\"original_question\":\"How many orders do I have?\",\"generated_sql\":\"SELECT COUNT(*) AS total_orders FROM orders WHERE user_id = 'test-user-123'\",\"query_results\":[{\"total_orders\":5}],\"natural_language_answer\":\"You have a total of 5 orders.\"}","session_id":"uuid","timestamp":"..."}
```

**SQL Event Types:**
- `sql_routing`: Classifying query type
- `sql_generating`: Generating SQL from natural language
- `sql_validating`: Validating SQL syntax and security
- `sql_executing`: Executing query against database
- `processing`: Formatting results into natural language

**SQL Query Examples:**

```bash
# Count orders
"How many orders do I have?"
→ SELECT COUNT(*) FROM orders WHERE user_id = 'user-123'

# List orders
"Show me all my orders"
→ SELECT * FROM orders WHERE user_id = 'user-123' ORDER BY order_date DESC

# Date range query
"Orders from last week"
→ SELECT * FROM orders WHERE user_id = 'user-123' AND order_date >= NOW() - INTERVAL '7 days'

# Aggregation
"What's my total spending?"
→ SELECT SUM(price * quantity) FROM orders WHERE user_id = 'user-123'

# Status filter
"Show my pending orders"
→ SELECT * FROM orders WHERE user_id = 'user-123' AND status = 'pending'
```

**Security Features:**
- Automatic `user_id` injection - users only see their own data
- SQL injection prevention via validation
- Only SELECT queries allowed (no INSERT, UPDATE, DELETE)
- Whitelist of allowed tables (`orders` only)
- Maximum result limit (default: 100 rows)
- Parameterized placeholder replacement

**Customer Service Routing:**

Non-SQL queries are automatically routed to customer service:

```bash
"My internet is not working"
→ Routed to customer service agent
→ Response: Technical Support category
```

### Document Search & Knowledge Base

The application includes a knowledge base for storing and searching documents with semantic search capabilities.

#### Upload Document

```bash
POST /api/documents
Content-Type: application/json

{
  "title": "Python Basics Tutorial",
  "content": "Python is a high-level programming language...",
  "file_type": "text",
  "metadata": {
    "category": "programming",
    "language": "python"
  }
}

Response:
{
  "document_id": "uuid",
  "title": "Python Basics Tutorial",
  "file_type": "text",
  "metadata": {
    "category": "programming",
    "language": "python"
  },
  "content_length": 245,
  "created_at": "2025-11-02T12:00:00",
  "updated_at": "2025-11-02T12:00:00"
}
```

#### List Documents

```bash
GET /api/documents?limit=50&offset=0

Response:
{
  "documents": [
    {
      "document_id": "uuid",
      "title": "Python Basics Tutorial",
      "file_type": "text",
      "metadata": {
        "category": "programming"
      },
      "content_length": 245,
      "created_at": "2025-11-02T12:00:00",
      "updated_at": "2025-11-02T12:00:00"
    }
  ],
  "total_count": 1,
  "limit": 50,
  "offset": 0
}
```

#### Get Document

```bash
GET /api/documents/{document_id}

Response:
{
  "document_id": "uuid",
  "title": "Python Basics Tutorial",
  "content": "Python is a high-level programming language...",
  "file_type": "text",
  "metadata": {
    "category": "programming",
    "language": "python"
  },
  "created_at": "2025-11-02T12:00:00",
  "updated_at": "2025-11-02T12:00:00"
}
```

#### Delete Document

```bash
DELETE /api/documents/{document_id}

Response:
{
  "document_id": "uuid",
  "deleted": true
}
```

#### Document Search via Chat

Documents are automatically searched when queries request information:

```bash
POST /api/stream-chat
Content-Type: application/json

{
  "message": "What is Python?",
  "user_id": "test-user-123",
  "session_id": "uuid"
}

Response: Server-Sent Events stream
data: {"event_type":"status","data":"Routing to document search...","session_id":"uuid","metadata":{"route":"document_search"}}

data: {"event_type":"doc_analyzing","data":"Analyzing search query...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"doc_retrieving","data":"Retrieving relevant documents...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"doc_ranking","data":"Ranking documents...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"doc_synthesizing","data":"Synthesizing answer...","session_id":"uuid","timestamp":"..."}

data: {"event_type":"final_response","data":"{\"original_query\":\"What is Python?\",\"retrieved_documents\":[{\"document_id\":\"uuid\",\"title\":\"Python Basics Tutorial\",\"snippet\":\"Python is a high-level programming language...\",\"relevance_score\":0.95}],\"answer\":\"Python is a high-level programming language that supports multiple programming paradigms...\",\"total_results\":3}","session_id":"uuid","timestamp":"..."}
```

**Document Search Event Types:**
- `doc_analyzing`: Query analysis and keyword extraction
- `doc_retrieving`: Retrieving relevant documents from knowledge base
- `doc_ranking`: Ranking documents by relevance
- `doc_synthesizing`: Generating natural language answer from documents

**Document Search Pipeline:**

The document search feature uses a multi-agent pipeline:

1. **Query Analyzer**: Extracts keywords and determines search intent
2. **Document Retriever**: Searches documents using text-based or embedding-based search
3. **Relevance Ranker**: Ranks retrieved documents by relevance score
4. **Answer Synthesizer**: Generates a natural language answer from top documents

**Search Query Examples:**

```bash
# Information queries
"What is FastAPI?"
"Explain machine learning"
"How to use Python decorators"

# Tutorial requests
"Show me Python tutorials"
"Find documentation about REST APIs"

# Concept explanations
"What are neural networks?"
"Explain microservices architecture"
```

**Search Features:**
- Text-based content search with keyword matching
- Metadata filtering for targeted search
- Relevance scoring and ranking
- Document snippets with context
- Natural language answer synthesis
- Future: Vector embedding-based semantic search

### Message Feedback

#### Update Message Feedback
```bash
POST /api/messages/{message_id}/feedback
Content-Type: application/json

{
  "feedback": "like"  # "like", "dislike", or null
}

Response:
{
  "message_id": "msg-uuid",
  "feedback": "like",
  "updated": true
}
```

**Feedback Toggle Behavior:**
- Click like when `null` → set to `"like"`
- Click like when `"like"` → set to `null`
- Click dislike when `"like"` → set to `"dislike"`
- Click dislike when `"dislike"` → set to `null`

### Legacy Endpoint

#### Process Inquiry (Non-streaming)
```bash
POST /api/process-inquiry
Content-Type: application/json

{
  "customer_inquiry": "My internet is not working"
}

Response:
{
  "original_inquiry": "My internet is not working",
  "category": "Technical Support",
  "suggested_response": "Thank you for contacting technical support. Please provide your account number and we will connect you with a specialist."
}
```

## 🧪 Testing

### Quick Test Script

```bash
USER_ID="test-user-123"

# 1. Create session
SESSION=$(curl -s -X POST "http://localhost:8000/api/create-session" \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER_ID\", \"title\": \"Test Chat\"}")
SESSION_ID=$(echo "$SESSION" | jq -r '.session_id')

# 2. List sessions
curl -s "http://localhost:8000/api/sessions?user_id=$USER_ID" | jq '.'

# 3. Update title
curl -s -X PATCH "http://localhost:8000/api/sessions/$SESSION_ID/title" \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated Title"}' | jq '.'

# 4. Delete session
curl -s -X DELETE "http://localhost:8000/api/sessions/$SESSION_ID" | jq '.'
```

## 🗄️ Database Schema

### chat_sessions
```sql
CREATE TABLE chat_sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### chat_messages
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    message_id UUID UNIQUE NOT NULL,
    session_id TEXT NOT NULL REFERENCES chat_sessions(session_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    feedback TEXT,
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### orders
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    order_date TIMESTAMP,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_sessions_user_id` on `chat_sessions(user_id)`
- `idx_sessions_updated_at` on `chat_sessions(updated_at)`
- `idx_session_id` on `chat_messages(session_id)`
- `idx_messages_user_id` on `chat_messages(user_id)`
- `idx_message_id` on `chat_messages(message_id)`
- `idx_timestamp` on `chat_messages(timestamp)`
- `idx_orders_user_id` on `orders(user_id)`
- `idx_orders_date` on `orders(order_date)`

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP POST/GET
       │
┌──────▼──────────────────────┐
│   FastAPI Application       │
│   - Rate Limiting (slowapi) │
│   - Request Validation      │
│   - SSE Streaming           │
└──────┬──────────────────────┘
       │
       ├──────────────┬─────────────────┐
       │              │                 │
┌──────▼──────┐  ┌───▼──────────┐  ┌──▼─────────────┐
│ PostgreSQL  │  │ Google ADK   │  │ SQLite (ADK)   │
│ (chat data) │  │ Multi-Agent  │  │ (agent state)  │
└─────────────┘  └──────────────┘  └────────────────┘
```

### Components

- **FastAPI**: Web framework with async support
- **PostgreSQL**: Primary database for chat history, sessions, and business data (orders)
- **Google ADK**: Agent Development Kit for multi-agent orchestration
- **RouterAgent**: Classifies queries as SQL/data queries or customer service inquiries
- **SQL Agent Pipeline**:
  - **SchemaRetriever**: Retrieves database schema information
  - **SqlGenerator**: Converts natural language to SQL queries
  - **SqlValidator**: Validates and secures SQL queries
  - **ResultFormatter**: Converts query results to natural language
- **Customer Service Pipeline**:
  - **CategorizerAgent**: Categorizes inquiries into "Technical Support", "Billing", or "General Inquiry"
  - **ResponderAgent**: Generates pre-defined responses based on category

## ⚙️ Configuration

### Rate Limits

| Endpoint | Limit | Purpose |
|----------|-------|---------|
| `/api/create-session` | 10/minute | Moderate usage |
| `/api/stream-chat` | 10/minute | Prevent API abuse |

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | Yes | - | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | Yes | `us-central1` | GCP region |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `TRUE` | Enable Vertex AI |
| `POSTGRES_USER` | Yes | `postgres` | PostgreSQL username |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL password |
| `POSTGRES_HOST` | No | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | No | `5432` | PostgreSQL port |
| `POSTGRES_DB` | Yes | `chat_history` | Database name |
| `SQL_ALLOWED_TABLES` | No | `orders` | Comma-separated list of tables for SQL queries |
| `SQL_MAX_RESULTS` | No | `100` | Maximum rows returned per query |

## 🚨 Troubleshooting

### Database Connection Errors

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection
psql -h localhost -U postgres -d chat_history -c "SELECT 1;"
```

### Tables Not Created

Tables are auto-created on first request. To manually create:

```bash
# Connect to database
psql -h localhost -U postgres -d chat_history

# Run migrations (handled automatically by FastAPI lifespan)
```

### Port Already in Use

```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or use different port
uvicorn main:app --port 8001
```

## 📊 Project Structure

```
agents_app/
├── main.py                          # FastAPI application (8 endpoints)
├── models.py                        # Pydantic models
├── chat_history_postgres.py         # PostgreSQL service
├── sql_query_service.py             # SQL query execution and security
├── requirements.txt                 # Dependencies
├── .env                             # Environment configuration
├── README.md                        # This file
├── agents/
│   ├── router/
│   │   ├── agent.py                 # Router orchestrator
│   │   └── llm_agent.py             # Query classification agent
│   ├── sql_agent/
│   │   ├── agent.py                 # SQL agent orchestrator
│   │   └── sub_agents/
│   │       ├── schema_retriever.py  # Database schema retrieval
│   │       ├── sql_generator.py     # NL to SQL conversion
│   │       ├── sql_validator.py     # SQL validation
│   │       └── result_formatter.py  # Results to NL conversion
│   └── customer_agent/
│       ├── agent.py                 # Agent orchestrator
│       └── sub_agents/
│           ├── categorizer.py       # Inquiry categorization
│           └── responder.py         # Response generation
└── multi_agent_data.db              # SQLite: Google ADK sessions
```

## 📦 Dependencies

```txt
fastapi                 # Web framework
uvicorn[standard]       # ASGI server
pydantic                # Data validation
google-adk              # Agent Development Kit
google-genai            # Gemini 2.0 Flash LLM
python-dotenv           # Environment variables
slowapi                 # Rate limiting
python-multipart        # Form data handling
aiofiles                # Async file operations
aiosqlite               # Async SQLite (for ADK)
asyncpg                 # PostgreSQL async driver
psycopg2-binary         # PostgreSQL adapter
```

## 🔐 Production Deployment

### Security Best Practices

1. Use strong PostgreSQL passwords
2. Enable HTTPS/TLS
3. Configure CORS properly
4. Use secrets manager for credentials
5. Enable authentication if needed
6. Monitor rate limits
7. Regular security audits

### Performance Tuning

1. Increase PostgreSQL connection pool size
2. Use multiple uvicorn workers: `--workers 4`
3. Configure proper database indexes (already done)
4. Implement caching for frequently accessed data
5. Monitor and optimize slow queries

### Monitoring

```bash
# Check API health
curl http://localhost:8000/

# View API documentation
open http://localhost:8000/docs

# Monitor PostgreSQL connections
psql -c "SELECT count(*) FROM pg_stat_activity;"
```

## 📝 API Rate Limiting

Rate limits are applied per IP address:

- **Create Session**: 10 requests/minute
- **Stream Chat**: 10 requests/minute
- **Other endpoints**: No limit

When rate limit is exceeded, API returns `429 Too Many Requests`.

## 🎯 Response Categories

The agent categorizes inquiries into:

1. **Technical Support**: Internet, connectivity, hardware issues
2. **Billing**: Payment, invoice, subscription questions
3. **General Inquiry**: All other questions

## 📈 Version History

- **v2.1.0** (2025-11-02): Text-to-SQL Feature
  - Added intelligent query routing (SQL vs customer service)
  - Text-to-SQL conversion with natural language responses
  - Multi-agent SQL pipeline (schema retrieval, generation, validation, formatting)
  - Orders table with business data
  - SQL security features (injection prevention, table whitelist, user_id filtering)
  - 6 new SQL-related stream event types

- **v2.0.0** (2025-11-02): Complete rewrite
  - Removed authentication system
  - Added session management
  - Added message feedback
  - PostgreSQL-only backend
  - SSE streaming only (removed WebSocket)
  - 8 REST endpoints

- **v1.0.0**: Initial release with auth and WebSocket support

## 📧 Support

For issues and questions:
- Check API docs: http://localhost:8000/docs
- View OpenAPI spec: http://localhost:8000/openapi.json

## 📄 License

[Your License Here]

---

**Built with FastAPI, PostgreSQL, and Google ADK** 🚀
