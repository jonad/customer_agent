import os
import uuid
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

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
