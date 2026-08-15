"""RAG-v1 FastAPI application."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from models.database import init_db
    from services.indexer import IndexerService
    init_db()
    IndexerService.get_instance().load()
    # warm up reranker model so first query isn't slow
    from services.reranker import _get_reranker
    _get_reranker()
    yield
    # Shutdown: nothing to do


app = FastAPI(title="RAG-v1", version="1.0.0", lifespan=lifespan)

from routers.upload import router as upload_router
from routers.chat import router as chat_router

app.include_router(upload_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# Serve frontend in production
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
