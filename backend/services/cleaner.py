"""Rule-based text cleaning — 纯规则、确定性、零 LLM。

原则：只做"删除/归一"，绝不改写内容（改写错一个数字 = 知识库里的假事实）。
页眉页脚靠两条腿：模式正则 + 跨页高频短行；重复段落按归一化文本精确去重。
"""
import re
from collections import Counter

# 页眉页脚/页码模式（整行匹配）
_PAGE_LINE_PATTERNS = [
    re.compile(r"^第\s*[0-9一二三四五六七八九十百]+\s*页(\s*共\s*[0-9一二三四五六七八九十百]+\s*页)?$"),
    re.compile(r"^-\s*\d+\s*-$"),          # "- 3 -"
    re.compile(r"^\d+\s*/\s*\d+$"),        # "3 / 12"
    re.compile(r"^(文档编号|编制|审批|审核|修订|密级)[:：]"),
    re.compile(r"^(内部资料|仅供内部使用|未经许可|版权所有|免责声明).*"),
]

_INVISIBLE_CHARS = {"​", "﻿", "‎", "‏"}
_HEADER_MIN_FREQ = 2     # 出现次数达到此值的短行视为页眉页脚（2 页文档页眉只出现 2 次）
_HEADER_MAX_LEN = 25
_SENT_ENDINGS = "。；：，！？"  # 以句末标点结尾的行视为正文，不按页眉删
_GARBAGE_MAX_RATIO = 0.3  # 段内异常字符占比上限，超则删段
_GARBAGE_DOC_RATIO = 0.5  # 全篇异常占比超此值 → 整篇乱码报错
_ILLEGAL_CHARS = re.compile(
    r"[^一-鿿　-〿＀-￯\x20-\x7e\n\t]"
)


def clean_text(text: str) -> str:
    # 1. 隐形字符/空白归一
    for ch in _INVISIBLE_CHARS:
        text = text.replace(ch, "")
    text = text.replace(" ", " ").replace("　", " ").replace("\r\n", "\n")
    lines = [l.strip() for l in text.split("\n")]

    # 2. 行级：模式正则 + 跨页高频短行（表格行不参与，标题行不误伤）
    counts = Counter(l for l in lines if l and not l.startswith("|"))
    headers = {
        l for l, c in counts.items()
        if c >= _HEADER_MIN_FREQ and len(l) <= _HEADER_MAX_LEN
        and not l.startswith("## ") and not l.endswith(tuple(_SENT_ENDINGS))
    }
    kept = [
        l for l in lines
        if not l or (not any(p.match(l) for p in _PAGE_LINE_PATTERNS) and l not in headers)
    ]
    removed_lines = len(lines) - len(kept)

    # 连续空行折叠为一个
    folded: list[str] = []
    for l in kept:
        if not l and folded and not folded[-1]:
            continue
        folded.append(l)

    # 3. 段落级：按归一化文本精确去重（忽略空白差异），保留首次出现
    paragraphs, seen, dup = [], set(), 0
    for para in "\n".join(folded).split("\n\n"):
        para = para.strip()
        if not para:
            continue
        key = re.sub(r"\s+", "", para)
        if key in seen:
            dup += 1
            continue
        seen.add(key)
        paragraphs.append(para)

    # 4. 乱码段删除 + 整篇乱码报错
    garbled = 0
    clean_paras = []
    for para in paragraphs:
        if len(_ILLEGAL_CHARS.findall(para)) / max(len(para), 1) > _GARBAGE_MAX_RATIO:
            garbled += 1
            continue
        clean_paras.append(para)

    total_chars = len(re.sub(r"\s+", "", text))
    if total_chars and garbled and sum(len(p) for p in clean_paras) / total_chars < (1 - _GARBAGE_DOC_RATIO):
        raise ValueError("文本乱码率过高，疑似编码错误")

    if removed_lines or dup or garbled:
        print(f"[清洗] 剔除页眉页脚/页码 {removed_lines} 行，去重 {dup} 段，删除乱码段 {garbled}")

    return "\n\n".join(clean_paras)
