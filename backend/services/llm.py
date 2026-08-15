"""DeepSeek streaming chat — receives pre-retrieved context from LangGraph."""
import asyncio
from openai import AsyncOpenAI
from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, HISTORY_TURNS
from models.database import get_messages, add_message, update_session

SYSTEM_PROMPT = """你是基于知识库的问答助手。请严格依据下面【资料】中的内容回答问题。
- 如果资料足以回答，请清晰作答并引用资料编号（如 [1]、[2]）。
- 如果资料不足以回答，请明确说"资料不足，无法回答"，可以给出一般性建议。
- 回答简洁，不要编造资料中没有的信息。"""


def _build_prompt(query: str, docs: list[dict], history: list[dict]) -> tuple[list[dict], list[dict]]:
    context_parts = []
    sources = []
    for i, d in enumerate(docs, 1):
        context_parts.append(f"[{i}] ({d['filename']})\n{d['text']}")
        sources.append({"index": i, "filename": d["filename"], "snippet": d["text"][:150]})

    context_str = "\n\n".join(context_parts) if context_parts else "（无相关资料）"

    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n【资料】\n{context_str}"}]

    recent = history[-(HISTORY_TURNS * 2):] if history else []
    for m in recent:
        messages.append({"role": m["role"], "content": m["content"]})

    messages.append({"role": "user", "content": query})
    return messages, sources


async def stream_chat(session_id: str, query: str, context: list[dict] | None = None):
    """Async generator yielding SSE event dicts.

    Args:
        session_id: chat session id
        query: user question
        context: pre-retrieved docs from LangGraph. If None, called without retrieval.
    """
    docs = context or []

    # Load history
    history = get_messages(session_id)
    prompt_msgs, sources = _build_prompt(query, docs, history)

    # Auto-title on first message
    if not history:
        title = query[:20] + ("…" if len(query) > 20 else "")
        update_session(session_id, title=title)

    yield {"type": "sources", "sources": sources}

    # Insert user message
    add_message(session_id, "user", query)

    client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    collected: list[str] = []

    try:
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=prompt_msgs,
            temperature=0.3,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                collected.append(delta.content)
                yield {"type": "delta", "content": delta.content}

    except asyncio.CancelledError:
        if collected:
            add_message(session_id, "assistant", "".join(collected))
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("LLM call failed")
        yield {"type": "error", "message": "LLM 调用失败，请稍后重试"}
        if collected:
            add_message(session_id, "assistant", "".join(collected))
        return

    # Save complete response
    full = "".join(collected)
    if full:
        add_message(session_id, "assistant", full)
    yield {"type": "done"}
