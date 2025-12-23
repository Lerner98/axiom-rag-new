"""
Memory Store
Handles conversation history storage with SQLite or Redis backends.
"""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class BaseMemoryStore(ABC):
    """Abstract base class for memory stores."""

    @abstractmethod
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to the conversation history."""
        pass

    @abstractmethod
    async def get_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        pass

    @abstractmethod
    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        pass

    @abstractmethod
    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        pass


class SQLiteMemoryStore(BaseMemoryStore):
    """SQLite-based conversation memory store."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(settings.memory_db_path)
        self._initialized = False

    async def _ensure_initialized(self):
        """Initialize the database if not already done."""
        if self._initialized:
            return

        import aiosqlite

        settings.data_dir.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    timestamp TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id ON messages(session_id)
            """)
            await db.commit()

        self._initialized = True
        logger.info(f"SQLite memory store initialized at {self.db_path}")

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to the conversation history."""
        await self._ensure_initialized()
        import aiosqlite

        timestamp = datetime.utcnow().isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, metadata_json, timestamp),
            )
            await db.commit()

    async def get_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        await self._ensure_initialized()
        import aiosqlite

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, role, content, metadata, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = await cursor.fetchall()

        # Return in chronological order
        messages = []
        for row in reversed(rows):
            msg = {
                "id": str(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            if row["metadata"]:
                msg["metadata"] = json.loads(row["metadata"])
            messages.append(msg)

        return messages

    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        await self._ensure_initialized()
        import aiosqlite

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            await db.commit()

    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        await self._ensure_initialized()
        import aiosqlite

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT DISTINCT session_id FROM messages ORDER BY session_id"
            )
            rows = await cursor.fetchall()

        return [row[0] for row in rows]


class RedisMemoryStore(BaseMemoryStore):
    """Redis-based conversation memory store."""

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or settings.redis_url
        self._client = None

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            import redis.asyncio as redis
            self._client = redis.from_url(self.redis_url)
            logger.info(f"Redis memory store connected to {self.redis_url}")
        return self._client

    def _key(self, session_id: str) -> str:
        """Generate Redis key for session."""
        return f"rag:memory:{session_id}"

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to the conversation history."""
        client = await self._get_client()

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata,
        }

        await client.rpush(self._key(session_id), json.dumps(message))

    async def get_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        client = await self._get_client()

        # Get last N messages
        messages_json = await client.lrange(self._key(session_id), -limit, -1)

        messages = []
        for msg_json in messages_json:
            msg = json.loads(msg_json)
            messages.append(msg)

        return messages

    async def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        client = await self._get_client()
        await client.delete(self._key(session_id))

    async def list_sessions(self) -> List[str]:
        """List all session IDs."""
        client = await self._get_client()
        keys = await client.keys("rag:memory:*")
        return [k.decode().replace("rag:memory:", "") for k in keys]


class MemoryStore:
    """
    Factory class that provides the appropriate memory store
    based on configuration.
    """

    _instance: Optional[BaseMemoryStore] = None

    @classmethod
    def get_store(cls) -> BaseMemoryStore:
        """Get or create the memory store instance."""
        if cls._instance is None:
            if settings.memory_backend == "redis":
                cls._instance = RedisMemoryStore()
            else:
                cls._instance = SQLiteMemoryStore()
            logger.info(f"Using {settings.memory_backend} memory backend")
        return cls._instance


# Convenience instance
memory_store = MemoryStore.get_store()
