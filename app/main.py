from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.storage.mongodb import ensure_indexes, mongo_lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.mongo_enabled:
        yield
        return
    async with mongo_lifespan() as client:
        database = client[settings.mongo_database]
        await client.admin.command("ping")
        await ensure_indexes(database)
        app.state.mongo_database = database
        yield

app = FastAPI(
    title="The Chaos Translator API",
    version="0.1.0",
    description="Source-grounded intelligence with local Qwen name extraction and Groq intelligence extraction.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "chaos-translator-api"}
