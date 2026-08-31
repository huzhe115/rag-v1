"""LangGraph RAG orchestration: route → resolve → retrieve → grade → rewrite loop → web fallback → context ready."""
import logging
from typing import TypedDict
from langgraph.graph import StateGraph, END
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from services.retriever import retrieve
from services.reranker import rerank
from services.tools import tavily_search

logger = logging.getLogger(__name__)


# ---------- State ----------

class RAGState(TypedDict):
    question: str
    original_question: str
    context: list[dict]
    retry_count: int
    is_sufficient: bool
    history: list[dict]  # 会话历史（最近几轮），用于指代消解
    steps: list[dict]  # 推理轨迹：[{step, detail}]，逐节点追加
    need_retrieval: bool  # 路由结果：该问题是否需要检索


# ---------- Nodes ----------

def route_node(state: RAGState) -> dict:
    """Routing：一次轻量 LLM 判断该问题是否需要检索知识库。

    在 resolve 之后执行——拿到指代消解后的完整问题再判断，
    避免"它…"这类追问因路由器看不到上下文而被误判为无需检索。
    闲聊、实时信息（时间）、库元信息（几份文档）等问题跳过检索管线。
    判断失败时默认需要检索（宁可多查不可漏查）。
    """
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    prompt = f"""判断以下用户问题是否需要检索知识库文档才能回答。
需要检索：问题要求基于库内文档内容回答（专业概念、文档细节、总结资料等）。
无需检索：纯闲聊、问候、实时信息（当前时间）、询问知识库本身状态（有几份文档）、常识问题。
只输出"需要"或"不需要"两个字。

问题：{state['question']}"""
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=8,
        )
        content = resp.choices[0].message.content.strip()
    except Exception:
        logger.exception("route classification failed, defaulting to retrieval")
        content = "需要"

    need = "需要" in content and "不" not in content
    detail = "需要检索 → 进入检索管线" if need else "无需检索 → 跳过检索，直接生成（工具/闲聊类问题）"
    logger.info("Route: %r → %s", state["question"], detail)
    return {
        "need_retrieval": need,
        "steps": state["steps"] + [{"step": "路由", "detail": detail}],
    }


def decide_route(state: RAGState) -> str:
    return "retrieve" if state["need_retrieval"] else "end"

def resolve_node(state: RAGState) -> dict:
    """结合历史消解指代，把"它/这个/第二个"还原为独立检索查询。

    改写结果只用于检索；生成阶段仍用原始问题 + 窗口内历史原文。
    无历史或改写失败时原样返回。
    """
    history = state.get("history") or []
    q = state["original_question"]
    if not history:
        return {"question": q}

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    dialog = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    prompt = f"""结合对话历史，把用户当前问题改写成独立完整的检索查询：
- 消解"它/这个/那个/第二个/前面说的"等指代，补全省略的主语和背景
- 如果当前问题本身已完整，原样输出
- 只输出改写后的查询，不要加任何解释

【对话历史】
{dialog}

【当前问题】
{q}"""
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        resolved = resp.choices[0].message.content.strip()
    except Exception:
        logger.exception("query resolve failed, using original question")
        resolved = ""

    if resolved and resolved != q:
        logger.info("Query resolved with history: %r → %r", q, resolved)
        return {
            "question": resolved,
            "steps": state["steps"] + [{"step": "指代消解", "detail": f"'{q}' → '{resolved}'"}],
        }
    return {
        "question": q,
        "steps": state["steps"] + [{"step": "指代消解", "detail": "问题已完整，无需改写"}],
    }


# ---------- Nodes ----------

def retrieve_node(state: RAGState) -> dict:
    """Hybrid search + rerank → context."""
    candidates = retrieve(state["question"], top_n=20)
    docs = rerank(state["question"], candidates)
    return {
        "context": docs,
        "steps": state["steps"] + [
            {"step": "混合检索", "detail": f"RRF 候选 {len(candidates)} 条 → rerank 精排留 {len(docs)} 条"}
        ],
    }


def grade_node(state: RAGState) -> dict:
    """Heuristic: top doc rerank_score > 0.5 → sufficient, else try rewrite."""
    ctx = state.get("context", [])
    if not ctx:
        return {
            "is_sufficient": False,
            "steps": state["steps"] + [{"step": "检索分级", "detail": "无候选结果，资料不足"}],
        }

    # If top result scores high, it's good enough
    top_score = ctx[0].get("rerank_score", 0)
    enough = top_score > 0.5
    return {
        "is_sufficient": enough,
        "steps": state["steps"] + [
            {"step": "检索分级", "detail": f"最高分 {top_score:.2f} → {'资料充分' if enough else '资料不足'}"}
        ],
    }


def rewrite_node(state: RAGState) -> dict:
    """Use LLM to rewrite the query for better retrieval."""
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    prompt = f"""你是一个搜索查询优化助手。用户的原始问题是：
"{state['original_question']}"

当前搜索词是："{state['question']}"
检索结果不够理想（第{state['retry_count'] + 1}次重试）。

请将问题重写为一个更好的搜索查询，用于在知识库中检索相关文档。要求：
- 提取核心关键词
- 补充可能的同义词或相关术语
- 只输出重写后的查询文本，不要加任何解释"""

    resp = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    new_query = resp.choices[0].message.content.strip()
    return {
        "question": new_query,
        "retry_count": state["retry_count"] + 1,
        "steps": state["steps"] + [
            {"step": "查询改写", "detail": f"第 {state['retry_count'] + 1} 次：→ '{new_query}'"}
        ],
    }


def web_search_node(state: RAGState) -> dict:
    """本地检索耗尽（2 次改写仍不足）→ Tavily 联网兜底，结果替换本地 context。

    走系统触发而非模型 tool calling：搜索权收在检索分级手里，避免模型滥用搜索。
    """
    query = state["original_question"]  # 用原始问题搜索，改写词是为本地检索优化的
    hits = tavily_search(query)

    web_docs = [
        {
            "id": f"web-{i}",
            "text": h["text"],
            "filename": h["title"],
            "url": h["url"],
            "score": h["score"],
            "rerank_score": h["score"],  # 复用字段，下游统一处理
            "source_type": "web",
        }
        for i, h in enumerate(hits, 1)
    ]
    logger.info("Web fallback triggered: query=%r hits=%d", query, len(web_docs))

    detail = f"Tavily 搜索 '{query}'，命中 {len(web_docs)} 条" if web_docs else f"Tavily 搜索无可用结果（原问题：'{query}'）"
    steps = state["steps"] + [{"step": "联网兜底", "detail": detail}]
    if web_docs:
        return {"context": web_docs, "steps": steps}
    # 搜不到好结果 → 保持原 context（多为空）
    return {"context": state.get("context", []), "steps": steps}


# ---------- Router ----------

def decide_next(state: RAGState) -> str:
    if state["is_sufficient"]:
        return "done"
    if state["retry_count"] >= 2:
        return "web"  # 改写用尽 → 联网兜底
    return "rewrite"


# ---------- Build Graph ----------

def build_rag_graph() -> StateGraph:
    workflow = StateGraph(RAGState)

    workflow.add_node("route", route_node)
    workflow.add_node("resolve", resolve_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("rewrite", rewrite_node)
    workflow.add_node("web", web_search_node)

    # 顺序：resolve（指代消解）→ route（拿完整问题判断是否需要检索）→ 检索管线或直接生成
    workflow.set_entry_point("resolve")
    workflow.add_edge("resolve", "route")
    workflow.add_conditional_edges("route", decide_route, {
        "retrieve": "retrieve",
        "end": END,
    })
    workflow.add_edge("retrieve", "grade")
    workflow.add_conditional_edges("grade", decide_next, {
        "done": END,
        "rewrite": "rewrite",
        "web": "web",
    })
    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("web", END)

    return workflow.compile()


# Singleton
_rag_graph = None


def get_rag_graph():
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = build_rag_graph()
    return _rag_graph
