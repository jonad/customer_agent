import os
import uuid
import json
from datetime import datetime
from typing import List, Optional
import asyncpg
from models import ChatMessage


class ChatHistoryServicePostgres:
    def __init__(self, connection_string: str = None):
        """
        Initialize PostgreSQL chat history service

        Args:
            connection_string: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
                If not provided, will construct from environment variables
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            # Construct from environment variables
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "postgres")
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            database = os.getenv("POSTGRES_DB", "chat_history")

            # Build connection string (omit password if empty for peer authentication)
            if password:
                self.connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
            else:
                self.connection_string = f"postgresql://{user}@{host}:{port}/{database}"

        self.pool = None

    async def get_pool(self):
        """Get or create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
        return self.pool

    async def init_db(self):
        """Initialize the chat history database tables"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Create chat_sessions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create chat_messages table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    message_id UUID UNIQUE NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    feedback TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
                )
            """)

            # Create indexes for chat_sessions
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON chat_sessions(user_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON chat_sessions(updated_at)
            """)

            # Create indexes for chat_messages
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_messages(timestamp)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_message_id ON chat_messages(message_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_user_id ON chat_messages(user_id)
            """)

            # Create orders table for SQL query demo
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price DECIMAL(10, 2) NOT NULL,
                    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for orders table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)
            """)

            # Insert sample data if table is empty
            count = await conn.fetchval("SELECT COUNT(*) FROM orders")
            if count == 0:
                await conn.execute("""
                    INSERT INTO orders (user_id, product_name, quantity, price, order_date, status) VALUES
                    ('test-user-123', 'Laptop', 1, 1299.99, NOW() - INTERVAL '2 days', 'delivered'),
                    ('test-user-123', 'Mouse', 2, 29.99, NOW() - INTERVAL '5 days', 'delivered'),
                    ('test-user-123', 'Keyboard', 1, 79.99, NOW() - INTERVAL '1 day', 'shipped'),
                    ('test-user-123', 'Monitor', 1, 399.99, NOW() - INTERVAL '10 days', 'delivered'),
                    ('test-user-123', 'USB Cable', 3, 9.99, NOW() - INTERVAL '3 days', 'delivered')
                """)

            # Create documents table for document search feature
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    document_id UUID UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    file_type TEXT,
                    file_path TEXT,
                    embedding JSONB,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for documents table
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_document_id ON documents(document_id)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)
            """)

            # GIN index for metadata JSONB queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN (metadata)
            """)

            # Insert sample documents if table is empty
            count = await conn.fetchval("SELECT COUNT(*) FROM documents")
            if count == 0:
                await conn.execute("""
                    INSERT INTO documents (document_id, title, content, file_type, metadata) VALUES
                    ($1, $2, $3, $4, $5),
                    ($6, $7, $8, $9, $10),
                    ($11, $12, $13, $14, $15)
                """,
                    str(uuid.uuid4()), 'Python Programming Guide',
                    'Python is a high-level, interpreted programming language. It supports multiple programming paradigms including procedural, object-oriented, and functional programming. Python is widely used for web development, data analysis, artificial intelligence, and automation.',
                    'text', '{"tags": ["programming", "python", "tutorial"], "author": "System"}',

                    str(uuid.uuid4()), 'Machine Learning Basics',
                    'Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience. Common algorithms include supervised learning (classification, regression), unsupervised learning (clustering), and reinforcement learning.',
                    'text', '{"tags": ["machine-learning", "ai", "data-science"], "author": "System"}',

                    str(uuid.uuid4()), 'FastAPI Framework Documentation',
                    'FastAPI is a modern, fast web framework for building APIs with Python. It features automatic OpenAPI documentation, async support, type hints validation with Pydantic, and high performance comparable to NodeJS and Go frameworks.',
                    'text', '{"tags": ["fastapi", "web-development", "api"], "author": "System"}'
                )

    async def store_message(self, message: ChatMessage) -> str:
        """Store a chat message and return the message ID"""
        message_id = message.message_id or str(uuid.uuid4())

        # Parse timestamp if it's a string
        if isinstance(message.timestamp, str):
            timestamp = datetime.fromisoformat(message.timestamp.replace('Z', '+00:00'))
        else:
            timestamp = message.timestamp or datetime.now()

        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO chat_messages
                (message_id, session_id, user_id, role, content, feedback, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (message_id)
                DO UPDATE SET
                    content = EXCLUDED.content,
                    feedback = EXCLUDED.feedback,
                    timestamp = EXCLUDED.timestamp
            """, uuid.UUID(message_id), message.session_id, message.user_id or "",
                 message.role, message.content, message.feedback, timestamp)

        return message_id

    async def get_session_history(self, session_id: str, limit: int = 50) -> List[ChatMessage]:
        """Retrieve chat history for a session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT message_id, session_id, user_id, role, content, feedback, timestamp
                FROM chat_messages
                WHERE session_id = $1
                ORDER BY timestamp ASC
                LIMIT $2
            """, session_id, limit)

            messages = []
            for row in rows:
                messages.append(ChatMessage(
                    message_id=str(row['message_id']),
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    role=row['role'],
                    content=row['content'],
                    feedback=row['feedback'],
                    timestamp=row['timestamp'].isoformat()
                ))

            return messages

    async def get_session_count(self, session_id: str) -> int:
        """Get total message count for a session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM chat_messages WHERE session_id = $1
            """, session_id)

            return result or 0

    async def delete_session_history(self, session_id: str) -> int:
        """Delete all messages for a session and return count of deleted messages"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM chat_messages WHERE session_id = $1
            """, session_id)

            # Extract count from result string like "DELETE 5"
            return int(result.split()[-1]) if result else 0

    async def get_conversation_context(self, session_id: str, limit: int = 10) -> str:
        """Get conversation context as formatted string for agent processing"""
        messages = await self.get_session_history(session_id, limit)

        if not messages:
            return ""

        context_lines = []
        for msg in messages:
            role_prefix = "User" if msg.role == "user" else "Assistant"
            context_lines.append(f"{role_prefix}: {msg.content}")

        return "\n".join(context_lines)

    async def create_session(self, session_id: str, user_id: str, title: str = "New Chat") -> dict:
        """Create a new chat session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            now = datetime.now()
            await conn.execute("""
                INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (session_id) DO NOTHING
            """, session_id, user_id, title, now, now)

            return {
                "session_id": session_id,
                "user_id": user_id,
                "title": title,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT EXISTS(SELECT 1 FROM chat_sessions WHERE session_id = $1)
            """, session_id)
            return result or False

    async def get_user_sessions(self, user_id: str) -> List[dict]:
        """Get all sessions for a user, ordered by most recently updated"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    s.session_id,
                    s.user_id,
                    s.title,
                    s.created_at,
                    s.updated_at,
                    COUNT(m.id) as message_count
                FROM chat_sessions s
                LEFT JOIN chat_messages m ON s.session_id = m.session_id
                WHERE s.user_id = $1
                GROUP BY s.session_id, s.user_id, s.title, s.created_at, s.updated_at
                ORDER BY s.updated_at DESC
            """, user_id)

            sessions = []
            for row in rows:
                sessions.append({
                    "session_id": row['session_id'],
                    "user_id": row['user_id'],
                    "title": row['title'],
                    "message_count": row['message_count'],
                    "created_at": row['created_at'].isoformat(),
                    "updated_at": row['updated_at'].isoformat()
                })

            return sessions

    async def update_session_title(self, session_id: str, title: str) -> bool:
        """Update the title of a session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE chat_sessions
                SET title = $1, updated_at = $2
                WHERE session_id = $3
            """, title, datetime.now(), session_id)

            # Check if any row was updated
            return result.split()[-1] != '0' if result else False

    async def update_session_timestamp(self, session_id: str) -> None:
        """Update the updated_at timestamp for a session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE chat_sessions
                SET updated_at = $1
                WHERE session_id = $2
            """, datetime.now(), session_id)

    async def delete_session(self, session_id: str) -> dict:
        """Delete a session and all its messages (CASCADE)"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Get message count before deletion
            message_count = await conn.fetchval("""
                SELECT COUNT(*) FROM chat_messages WHERE session_id = $1
            """, session_id)

            # Delete session (messages will be cascade deleted)
            result = await conn.execute("""
                DELETE FROM chat_sessions WHERE session_id = $1
            """, session_id)

            deleted = result.split()[-1] != '0' if result else False

            return {
                "session_id": session_id,
                "deleted": deleted,
                "messages_deleted": message_count or 0
            }

    async def update_message_feedback(self, message_id: str, feedback: Optional[str]) -> bool:
        """Update the feedback (like/dislike) for a message"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE chat_messages
                SET feedback = $1
                WHERE message_id = $2
            """, feedback, uuid.UUID(message_id))

            # Check if any row was updated
            return result.split()[-1] != '0' if result else False

    async def auto_generate_title(self, session_id: str) -> Optional[str]:
        """Auto-generate a title from the first user message in a session"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Get the first user message
            first_message = await conn.fetchrow("""
                SELECT content FROM chat_messages
                WHERE session_id = $1 AND role = 'user'
                ORDER BY timestamp ASC
                LIMIT 1
            """, session_id)

            if not first_message:
                return None

            # Generate title from first 50 characters
            content = first_message['content']
            title = content[:50].replace('\n', ' ').strip()
            if len(content) > 50:
                title += "..."

            # Update the session title
            await conn.execute("""
                UPDATE chat_sessions
                SET title = $1, updated_at = $2
                WHERE session_id = $3
            """, title, datetime.now(), session_id)

            return title

    # Document management methods
    async def store_document(self, document_id: str, title: str, content: str,
                            file_type: str = None, file_path: str = None,
                            embedding: list = None, metadata: dict = None) -> dict:
        """Store a new document with optional embedding"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Convert embedding list to JSONB
            embedding_json = json.dumps(embedding) if embedding else None
            metadata_json = json.dumps(metadata) if metadata else None

            await conn.execute("""
                INSERT INTO documents (document_id, title, content, file_type, file_path, embedding, metadata)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb)
            """, uuid.UUID(document_id), title, content, file_type, file_path, embedding_json, metadata_json)

            return {
                "document_id": document_id,
                "title": title,
                "created_at": datetime.now().isoformat()
            }

    async def get_document(self, document_id: str) -> Optional[dict]:
        """Get a single document by ID"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT document_id, title, content, file_type, file_path, embedding, metadata, created_at, updated_at
                FROM documents
                WHERE document_id = $1
            """, uuid.UUID(document_id))

            if row:
                # Parse JSONB fields from strings to dicts/lists
                embedding = json.loads(row['embedding']) if row['embedding'] and isinstance(row['embedding'], str) else row['embedding']
                metadata = json.loads(row['metadata']) if row['metadata'] and isinstance(row['metadata'], str) else row['metadata']

                return {
                    "document_id": str(row['document_id']),
                    "title": row['title'],
                    "content": row['content'],
                    "file_type": row['file_type'],
                    "file_path": row['file_path'],
                    "embedding": embedding,
                    "metadata": metadata,
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                }
            return None

    async def get_all_documents(self, limit: int = 50, offset: int = 0) -> dict:
        """Get all documents with pagination"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT document_id, title, file_type, metadata, created_at, updated_at,
                       LENGTH(content) as content_length
                FROM documents
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)

            total = await conn.fetchval("SELECT COUNT(*) FROM documents")

            documents = []
            for row in rows:
                # Parse JSONB fields from strings to dicts
                metadata = json.loads(row['metadata']) if row['metadata'] and isinstance(row['metadata'], str) else row['metadata']

                documents.append({
                    "document_id": str(row['document_id']),
                    "title": row['title'],
                    "file_type": row['file_type'],
                    "metadata": metadata,
                    "content_length": row['content_length'],
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None,
                    "updated_at": row['updated_at'].isoformat() if row['updated_at'] else None
                })

            return {
                "documents": documents,
                "total_count": total,
                "limit": limit,
                "offset": offset
            }

    async def search_documents_by_content(self, query: str, limit: int = 10) -> list:
        """Simple text-based search in document content and title"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT document_id, title, content, file_type, metadata, created_at
                FROM documents
                WHERE title ILIKE $1 OR content ILIKE $1
                ORDER BY created_at DESC
                LIMIT $2
            """, f"%{query}%", limit)

            results = []
            for row in rows:
                # Extract snippet around match
                content = row['content']
                query_lower = query.lower()
                idx = content.lower().find(query_lower)
                if idx >= 0:
                    start = max(0, idx - 50)
                    end = min(len(content), idx + len(query) + 50)
                    snippet = content[start:end].strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                else:
                    snippet = content[:100] + "..." if len(content) > 100 else content

                results.append({
                    "document_id": str(row['document_id']),
                    "title": row['title'],
                    "file_type": row['file_type'],
                    "metadata": row['metadata'],
                    "snippet": snippet,
                    "created_at": row['created_at'].isoformat() if row['created_at'] else None
                })

            return results

    async def search_documents_semantic(self, query_embedding: list, limit: int = 10, threshold: float = 0.5) -> list:
        """
        Semantic search using embedding similarity
        Uses cosine similarity to find the most relevant documents

        Args:
            query_embedding: Embedding vector of the search query
            limit: Maximum number of results to return
            threshold: Minimum similarity score (0.0 to 1.0)

        Returns:
            List of documents with relevance scores, sorted by similarity
        """
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            # Retrieve all documents with embeddings
            rows = await conn.fetch("""
                SELECT document_id, title, content, file_type, metadata, embedding, created_at
                FROM documents
                WHERE embedding IS NOT NULL
            """)

            results = []
            for row in rows:
                try:
                    # Parse the embedding from JSONB
                    doc_embedding = json.loads(row['embedding']) if isinstance(row['embedding'], str) else row['embedding']

                    if not doc_embedding:
                        continue

                    # Calculate cosine similarity
                    similarity = self._calculate_cosine_similarity(query_embedding, doc_embedding)

                    if similarity >= threshold:
                        # Create snippet from first 150 characters
                        content = row['content']
                        snippet = content[:150] + "..." if len(content) > 150 else content

                        results.append({
                            "document_id": str(row['document_id']),
                            "title": row['title'],
                            "file_type": row['file_type'],
                            "metadata": row['metadata'],
                            "snippet": snippet,
                            "relevance_score": similarity,
                            "created_at": row['created_at'].isoformat() if row['created_at'] else None
                        })
                except Exception as e:
                    print(f"Error processing document {row.get('document_id')}: {e}")
                    continue

            # Sort by relevance score descending
            results.sort(key=lambda x: x['relevance_score'], reverse=True)

            return results[:limit]

    def _calculate_cosine_similarity(self, vec1: list, vec2: list) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Calculate magnitudes
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity
        return dot_product / (magnitude1 * magnitude2)

    async def update_document_embedding(self, document_id: str, embedding: list) -> bool:
        """Update the embedding for a document"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            embedding_json = json.dumps(embedding)
            result = await conn.execute("""
                UPDATE documents
                SET embedding = $1::jsonb, updated_at = $2
                WHERE document_id = $3
            """, embedding_json, datetime.now(), uuid.UUID(document_id))

            return result.split()[-1] != '0' if result else False

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM documents WHERE document_id = $1
            """, uuid.UUID(document_id))

            return result.split()[-1] != '0' if result else False

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
