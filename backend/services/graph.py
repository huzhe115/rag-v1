"""LangGraph RAG orchestration: retrieve → grade → rewrite loop → context ready."""
from typing import TypedDict
from langgraph.graph import StateGraph, END
from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from services.retriever import retrieve
from services.reranker import rerank


# ---------- State ----------

class RAGState(TypedDict):
    question: str
    original_question: str
    context: list[dict]
    retry_count: int
    is_sufficient: bool


# ---------- Nodes ----------

def retrieve_node(state: RAGState) -> dict:
    """Hybrid search + rerank → context."""
    candidates = retrieve(state["question"], top_n=20)
    docs = rerank(state["question"], candidates)
    return {"context": docs}


def grade_node(state: RAGState) -> dict:
    """Heuristic: top doc rerank_score > 0.5 → sufficient, else try rewrite."""
    ctx = state.get("context", [])
    if not ctx:
        return {"is_sufficient": False}

    # If top result scores high, it's good enough
    top_score = ctx[0].get("rerank_score", 0)
    return {"is_sufficient": top_score > 0.5}


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
    }


# ---------- Router ----------

def decide_next(state: RAGState) -> str:
    if state["is_sufficient"]:
        return "done"
    if state["retry_count"] >= 2:
        return "done"  # give up after 2 rewrites
    return "rewrite"


# ---------- Build Graph ----------

def build_rag_graph() -> StateGraph:
    workflow = StateGraph(RAGState)

    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("rewrite", rewrite_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade")
    workflow.add_conditional_edges("grade", decide_next, {
        "done": END,
        "rewrite": "rewrite",
    })
    workflow.add_edge("rewrite", "retrieve")

    return workflow.compile()


# Singleton
_rag_graph = None


def get_rag_graph():
    global _rag_graph
    if _rag_graph is None:
        _rag_graph = build_rag_graph()
    return _rag_graph
