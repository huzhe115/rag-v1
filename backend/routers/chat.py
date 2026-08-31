"""Chat SSE streaming + session CRUD. Uses LangGraph for retrieval loop."""
import json
import asyncio
import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from models.database import (
    create_session, list_sessions, get_session, delete_session, get_messages,
    add_trace, get_traces,
)
from services.graph import get_rag_graph
from services.llm import stream_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


# ---------- SSE generators ----------

async def _sse_generator(session_id: str, query: str):
    """Run LangGraph retrieval loop → stream DeepSeek response → persist trace."""
    t0 = time.time()
    tool_log: list[dict] = []
    graph_state: dict = {}
    context: list[dict] = []
    try:
        # Phase 1: LangGraph retrieval（带历史指代消解 + 检索分级，逐步记录决策）
        graph = get_rag_graph()
        graph_state = await asyncio.to_thread(
            graph.invoke,
            {
                "question": query,
                "original_question": query,
                "context": [],
                "retry_count": 0,
                "is_sufficient": False,
                "history": get_messages(session_id),
                "steps": [],
                "need_retrieval": True,
            },
        )

        context = graph_state.get("context", [])
        retries = graph_state.get("retry_count", 0)
        if retries > 0:
            import logging
            logging.getLogger(__name__).info(
                f"Query rewritten {retries} time(s): '{query}' → '{graph_state.get('question', query)}'"
            )

        # Phase 2: Stream LLM generation with retrieved context（工具调用记录进 tool_log）
        async for event in stream_chat(session_id, query, context, tool_log=tool_log):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    except asyncio.CancelledError:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as e:
        # 检索/embedding 等异常也要发 error+done，否则前端永远停在"正在生成"
        import logging
        logging.getLogger(__name__).exception("SSE stream failed")
        yield f"data: {json.dumps({'type': 'error', 'message': '服务内部错误，请稍后重试'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    finally:
        # Phase 3: 持久化推理轨迹（检索决策 + 工具调用 + 总耗时）
        steps = list(graph_state.get("steps", []))
        steps.append({
            "step": "生成",
            "detail": f"引用来源 {len(context)} 条，耗时 {time.time() - t0:.1f}s",
        })
        steps.extend(tool_log)
        try:
            add_trace(session_id, query, steps)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("trace persist failed")


# ---------- Chat ----------

@router.post("/chat/{session_id}")
async def chat(session_id: str, req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "消息不能为空")
    if len(req.message) > 4000:
        raise HTTPException(400, "消息过长（上限 4000 字符）")
    if not get_session(session_id):
        raise HTTPException(404, "会话不存在")

    return StreamingResponse(
        _sse_generator(session_id, req.message.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- Sessions ----------

@router.get("/sessions")
def list_sessions_route():
    return list_sessions()


@router.post("/sessions")
def create_session_route():
    return create_session()


@router.delete("/sessions/{session_id}")
def delete_session_route(session_id: str):
    delete_session(session_id)
    return {"ok": True}


@router.get("/sessions/{session_id}/messages")
def get_session_messages(session_id: str):
    return get_messages(session_id)


@router.get("/sessions/{session_id}/traces")
def get_session_traces(session_id: str):
    """推理轨迹：每轮提问的检索决策、工具调用与耗时。"""
    if not get_session(session_id):
        raise HTTPException(404, "会话不存在")
    return get_traces(session_id)
