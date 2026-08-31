"""RAG-v1 FastAPI application."""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
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


# Serve frontend in production (SPA fallback：未知路径回退 index.html，刷新 /chat 不再 404)
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(404, "Not Found")
        candidate = frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)  # dist 里的静态资源
        return FileResponse(frontend_dist / "index.html")  # SPA 路由 → 回退首页
