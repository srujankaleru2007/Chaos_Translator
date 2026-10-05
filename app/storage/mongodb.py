"""MongoDB lifecycle and persistence primitives."""

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from app.core.config import settings


class MongoUnavailable(RuntimeError):
    """Raised when MongoDB support is not installed or cannot be reached."""


def create_client() -> Any:
    try:
        from pymongo import AsyncMongoClient
    except ImportError as exc:  # pragma: no cover
        raise MongoUnavailable("MongoDB support requires the pymongo dependency.") from exc
    return AsyncMongoClient(
        settings.mongo_uri,
        serverSelectionTimeoutMS=settings.mongo_server_selection_timeout_ms,
    )


@asynccontextmanager
async def mongo_lifespan() -> AsyncIterator[Any]:
    """Yield one process-wide client and close it during application shutdown."""
    client = create_client()
    try:
        yield client
    finally:
        await client.close()


async def ensure_indexes(database: Any) -> None:
    """Create stable indexes for the first persistence collections."""
    await database.sources.create_index([("workspace_id", 1), ("created_at", -1)])
    await database.extractions.create_index([("workspace_id", 1), ("created_at", -1)])
    await database.extractions.create_index([("source_id", 1)])


class MongoRepository:
    """Workspace-scoped persistence for source text and extraction results."""

    def __init__(self, database: Any):
        self.sources = database.sources
        self.extractions = database.extractions

    async def save_source(self, document: dict[str, Any]) -> str:
        result = await self.sources.insert_one(document)
        return str(result.inserted_id)

    async def save_extraction(self, document: dict[str, Any]) -> str:
        result = await self.extractions.insert_one(document)
        return str(result.inserted_id)

    async def list_sources(self, workspace_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        cursor = self.sources.find({"workspace_id": workspace_id}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
