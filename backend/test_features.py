"""功能冒烟测试：用 traces 断言路由/工具调用/多轮行为（回答质量评测雏形）。

真实跑对话 API，覆盖：路由跳检、时间工具、文档清单工具、检索引用、
多轮指代消解、全历史记忆、库外问题兜底/拒绝。消耗少量 LLM 额度。

运行：cd backend && python test_features.py
"""
import asyncio
import json
import sys

from models.database import init_db, create_session, delete_session, get_traces
from routers.chat import _sse_generator

PASS, FAIL = 0, 0


def check(name: str, cond: bool, info=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ {name}  实际: {info[:120]}")


async def ask(sid: str, q: str) -> tuple[str, list[dict]]:
    """跑一轮对话，返回 (回答文本, 最新一条轨迹步骤)。"""
    lines = []
    async for raw in _sse_generator(sid, q):
        lines.append(raw)
    events = [json.loads(l[6:]) for l in lines if l.startswith("data:")]
    answer = "".join(e["content"] for e in events if e["type"] == "delta")
    traces = get_traces(sid)
    steps = traces[0]["steps"] if traces else []
    return answer, steps


def names(steps: list[dict]) -> list[str]:
    return [s["step"] for s in steps]


def detail(steps: list[dict], name: str) -> str:
    return next((s["detail"] for s in steps if s["step"] == name), "")


async def main():
    init_db()
    sid = create_session()["id"]

    # 1. 闲聊：路由跳过检索
    print("\n[1] 闲聊路由")
    ans, steps = await ask(sid, "你好")
    check("闲聊跳过检索", "混合检索" not in names(steps), str(names(steps)))
    check("路由判定无需检索", "无需检索" in detail(steps, "路由"), detail(steps, "路由"))

    # 2. 时间工具：跳过检索 + 工具被调用 + 回答有真实时间
    print("\n[2] 时间查询")
    ans, steps = await ask(sid, "现在几点了？")
    check("时间问题跳过检索", "混合检索" not in names(steps), str(names(steps)))
    check("时间工具被调用", "工具调用" in names(steps), str(names(steps)))
    check("回答包含时间", ":" in ans or ("点" in ans and "分" in ans), ans[:80])

    # 3. 文档清单工具
    print("\n[3] 文档清单查询")
    ans, steps = await ask(sid, "知识库里有几份文档？")
    check("文档查询跳过检索", "混合检索" not in names(steps), str(names(steps)))
    check("文档工具被调用", "工具调用" in names(steps), str(names(steps)))
    check("回答包含份数", "份文档" in ans, ans[:80])

    # 4. 内容问题：正常检索 + 引用
    print("\n[4] 内容检索")
    ans, steps = await ask(sid, "数据中台建设方案讲了什么？")
    check("内容问题进入检索", "混合检索" in names(steps), str(names(steps)))
    check("路由判定需要检索", "需要检索" in detail(steps, "路由"), detail(steps, "路由"))
    check("回答带引用编号", "[1]" in ans, ans[:300])

    # 5. 多轮指代消解：追问"它"应被还原
    print("\n[5] 多轮指代消解")
    ans, steps = await ask(sid, "它的核心目标是什么？")
    check("指代消解被触发", "指代消解" in names(steps), str(names(steps)))
    check("指代被改写为完整查询", "→" in detail(steps, "指代消解"), detail(steps, "指代消解"))

    # 6. 全历史记忆：第一个问题能答上来
    print("\n[6] 全历史记忆")
    ans, steps = await ask(sid, "我的第一个问题是什么？")
    check("记得第一个问题", "几点" in ans, ans[:100])

    # 7. 库外问题：联网兜底 或 明确拒绝（取决于 TAVILY 是否可用）
    print("\n[7] 库外问题兜底")
    ans, steps = await ask(sid, "2026年诺贝尔物理学奖颁给了谁？")
    has_web = "联网兜底" in names(steps)
    refused = "资料不足" in ans or "无法回答" in ans
    check("走联网兜底或明确拒绝", has_web or refused, str(names(steps)))

    delete_session(sid)
    print(f"\n结果: {PASS} 通过 / {FAIL} 失败")
    sys.exit(1 if FAIL else 0)


asyncio.run(main())
