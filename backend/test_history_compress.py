"""History compaction smoke test: full-window memory, 65% fold gating, boundary marker."""
import asyncio
from types import SimpleNamespace

from models.database import init_db, create_session, get_session, delete_session
from services.llm import _build_prompt, _msg_tokens, _needs_compact, _maybe_compress


class FakeClient:
    """Stub AsyncOpenAI: counts calls, returns fixed summary."""
    calls = 0

    class chat:
        class completions:
            @staticmethod
            async def create(**kw):
                FakeClient.calls += 1
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="压缩摘要"))])


def test_pure():
    assert _msg_tokens([{"content": "ab"}, {"content": "cd"}]) == 4

    # 窗口装全部历史（不再只保留最近 3 轮）→ "第一个问题" 也在 prompt 里
    history = [{"role": "user", "content": f"q{i}", "id": i} for i in range(1, 9)]
    msgs, sources = _build_prompt("当前问题", [], history, "")
    user_msgs = [m["content"] for m in msgs if m["role"] == "user"]
    assert user_msgs == ["q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8", "当前问题"]

    msgs2, _ = _build_prompt("当前问题", [], [], "历史摘要")
    assert "【对话历史摘要】" in msgs2[0]["content"]
    print("ok: pure helpers")


def test_compact():
    init_db()
    sid = create_session()["id"]
    fake = FakeClient()

    # 1. 短窗口：未超 65% → 不折叠
    short = [{"role": "user", "content": "短", "id": i} for i in range(1, 9)]
    short_msgs, _ = _build_prompt("当前问题", [], short, "")
    assert not _needs_compact(short_msgs)

    # 2. 无窗口外历史（≤3 轮）→ 不调 LLM
    tiny = [{"role": "user", "content": "短", "id": i} for i in range(1, 5)]
    assert asyncio.run(_maybe_compress(fake, sid, tiny, "")) == ""
    assert fake.calls == 0

    # 3. 超 65% → 折叠触发：摘要落库 + 折叠标记推进到窗口外最后一条
    long = [{"role": "user", "content": "长" * 1000, "id": i} for i in range(1, 61)]
    long_msgs, _ = _build_prompt("当前问题", [], long, "")
    assert _needs_compact(long_msgs)
    summary = asyncio.run(_maybe_compress(fake, sid, long, ""))
    assert fake.calls == 1 and summary == "压缩摘要"
    sess = get_session(sid)
    assert sess["summary"] == "压缩摘要" and sess["summary_upto"] == 54  # 60 条 - 最近 6 条窗口

    # 4. 折叠后重建：窗口 = 标记之后的 6 条 + 摘要注入 system
    uncompacted = [m for m in long if m["id"] > sess["summary_upto"]]
    msgs, _ = _build_prompt("当前问题", [], uncompacted, summary)
    user_msgs = [m["content"] for m in msgs if m["role"] == "user"]
    assert len(user_msgs) == 7 and user_msgs[-1] == "当前问题"
    assert "【对话历史摘要】" in msgs[0]["content"]

    # 5. 增量：新消息到来再次折叠，旧摘要进 prompt 合并
    long2 = long + [{"role": "user", "content": "新" * 1000, "id": i} for i in range(61, 70)]
    asyncio.run(_maybe_compress(fake, sid, long2, summary))
    assert fake.calls == 2

    delete_session(sid)
    print("ok: fold gating/boundary/persist")


test_pure()
test_compact()
