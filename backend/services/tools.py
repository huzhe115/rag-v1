"""LLM tools: 时间查询（模型主动调用）+ Tavily 联网搜索（系统兜底，不给模型自由调用权）。"""
import json
import logging
from datetime import datetime

from config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

_WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


# ---------- 工具 1：get_current_time（真 tool calling，模型按需调用） ----------

TIME_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "获取当前日期和时间。当用户询问现在几点、今天几号、距离某日期还有多久等时间相关问题时调用，不要凭空猜测日期时间。",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_current_time() -> str:
    now = datetime.now().astimezone()
    tz = now.strftime("%z")
    return (
        f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')} {_WEEKDAYS[now.weekday()]}"
        f"（UTC{tz[:3]}:{tz[3:]}）"
    )


# ---------- 工具 3：list_documents（知识库元信息，模型按需查询） ----------

LIST_DOCS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_documents",
        "description": "查询知识库元信息：库里共有几份文档、每份的文件名、分块数和上传日期。当用户询问知识库里有多少/有哪些文档时调用，不要凭空猜测。",
        "parameters": {"type": "object", "properties": {}},
    },
}


def list_documents() -> str:
    from models.database import list_documents as _list_docs
    docs = _list_docs()
    if not docs:
        return "知识库当前没有任何文档。"
    lines = [f"知识库共 {len(docs)} 份文档："]
    for d in docs:
        lines.append(f"- {d['filename']}（{d['chunk_count']} 个分块，上传于 {d['created_at'][:10]}）")
    return "\n".join(lines)


def execute_tool(name: str, arguments: dict) -> str:
    """执行模型请求的工具，返回给模型的 tool result 文本。"""
    if name == "get_current_time":
        return get_current_time()
    if name == "list_documents":
        return list_documents()
    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)


# ---------- 工具 2：tavily_search（系统兜底用，模型不可见） ----------

def tavily_search(query: str, max_results: int | None = None) -> list[dict]:
    """联网搜索兜底。返回 [{title, url, text, score}, ...]，低相关分结果直接丢弃。

    设计说明：不走模型 tool calling，由检索分级流程在本地资料不足时触发，
    避免模型滥用搜索引入噪声（详见 graph.py web_search_node）。
    """
    if not TAVILY_API_KEY:
        return []
    try:
        from tavily import TavilyClient
    except ImportError:
        logger.warning("tavily-python 未安装，联网兜底禁用")
        return []

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        resp = client.search(
            query=query,
            search_depth="basic",
            max_results=max_results or TAVILY_MAX_RESULTS,
            include_answer=False,
        )
    except Exception:
        logger.exception("Tavily search failed for query=%r", query)
        return []

    results = []
    for r in resp.get("results", []):
        score = r.get("score", 0.0)
        if score < TAVILY_SCORE_THRESHOLD:
            continue
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "text": (r.get("content") or "")[:600],
            "score": score,
        })
    return results
