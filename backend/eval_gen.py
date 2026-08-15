"""端到端生成质量评测（RAGAS 风格，LLM 裁判，不依赖 ragas 库）。

指标：
- Answer Correctness：生成答案与评测集标准答案语义是否一致（0/1）
- Faithfulness：生成答案是否完全由检索资料支撑（有无编造，0/1）

链路：retrieve → rerank → DeepSeek 生成 → deepseek-chat 裁判。
用法：cd backend && python eval_gen.py
"""
import asyncio
import json
import re
from collections import OrderedDict
from pathlib import Path

from openai import AsyncOpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from eval import load_qa
from services.retriever import retrieve
from services.reranker import rerank
from services.llm import _build_prompt

JUDGE_CORRECT = """你是评测裁判。判断 AI 答案与标准答案在语义上是否一致（表述差异不算错，事实错误算错）。
标准答案：{gold}
AI 答案：{answer}
只输出 JSON：{{"score": 0 或 1, "reason": "一句话理由"}}"""

JUDGE_FAITHFUL = """你是评测裁判。判断 AI 答案是否完全由给定资料支持，有没有编造资料中没有的事实。
【资料】
{context}

AI 答案：{answer}
只输出 JSON：{{"score": 0 或 1, "reason": "一句话理由"}}"""


def _parse_score(text: str) -> tuple[int, str]:
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0))
    return int(data["score"]), data.get("reason", "")


async def main():
    qa = load_qa()
    # 每文档最多取 2 题，稳定抽样（可复现）
    by_doc: "OrderedDict[str, list]" = OrderedDict()
    for q in qa:
        by_doc.setdefault(q["doc"], []).append(q)
    sampled = [q for qs in by_doc.values() for q in qs[:2]]
    print(f"抽题 {len(sampled)} 道，裁判模型 {LLM_MODEL}\n")

    client = AsyncOpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    async def chat(messages: list[dict]) -> str:
        resp = await client.chat.completions.create(
            model=LLM_MODEL, messages=messages, temperature=0.3)
        return resp.choices[0].message.content or ""

    correct_total = faithful_total = 0
    failures = []
    for i, q in enumerate(sampled, 1):
        docs = rerank(q["question"], retrieve(q["question"], top_n=20))
        messages, _ = _build_prompt(q["question"], docs, None)
        answer = await chat(messages)

        gold = "；".join(q["answers"])
        c_score, c_reason = _parse_score(await chat([
            {"role": "user", "content": JUDGE_CORRECT.format(gold=gold, answer=answer)}]))
        # 裁判的资料与生成端一致（system prompt + 带 [i] 编号的资料）
        context = messages[0]["content"]
        f_score, f_reason = _parse_score(await chat([
            {"role": "user", "content": JUDGE_FAITHFUL.format(context=context, answer=answer)}]))

        correct_total += c_score
        faithful_total += f_score
        flag = "✅" if (c_score and f_score) else "❌"
        print(f"{flag} [{i:2d}/{len(sampled)}] {q['question'][:30]} 正确={c_score} 忠实={f_score}")
        if not (c_score and f_score):
            failures.append((q, answer, c_reason, f_reason))

    n = len(sampled)
    print(f"\nAnswer Correctness: {correct_total}/{n} = {correct_total / n:.1%}")
    print(f"Faithfulness:      {faithful_total}/{n} = {faithful_total / n:.1%}")

    if failures:
        print("\n失败样本：")
        for q, answer, cr, fr in failures:
            print(f"\nQ: {q['question']}")
            print(f"A: {answer[:120]}")
            print(f"  正确性: {cr}")
            print(f"  忠实度: {fr}")


if __name__ == "__main__":
    asyncio.run(main())
