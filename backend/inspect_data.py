"""语料体检：统计 data/ 与 store/documents/ 下文档的解析难度特征。

用法：cd backend && python inspect_data.py
输出：每页文本层字符数（判断扫描页）、表格数、图片数、字号分布（判断标题推断可行性）、
      txt 重复行（判断页眉页脚严重程度）。
"""
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf as fitz

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_DOCS = Path(__file__).resolve().parent / "store" / "documents"
SCAN_THRESHOLD = 30  # 每页文本层字符数低于此值视为扫描页


def inspect_pdf(path: Path) -> None:
    doc = fitz.open(str(path))
    print(f"\n== PDF: {path.name} | 页数 {len(doc)}")
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        tables = page.find_tables()
        images = page.get_image_info()
        sizes = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span["text"].strip():
                        sizes.append(round(span["size"], 1))
        body_size = Counter(sizes).most_common(1)[0][0] if sizes else 0
        heads = [s for s in sizes if s > body_size + 1.5]
        flag = "⚠ 疑似扫描页" if len(text) < SCAN_THRESHOLD else ""
        print(f"  页{i+1}: 文本{len(text)}字 {flag} | 表格{len(tables.tables)} | 图片{len(images)}"
              f" | 字号分布{Counter(sizes).most_common(3)} | 大字号行≥{len(heads)}")


def inspect_txt(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    dup = Counter(lines)
    repeats = {l: c for l, c in dup.items() if c > 1}
    invisible = len(re.findall(r"[ ​﻿]", text))
    print(f"\n== TXT: {path.name} | {len(lines)}非空行 | 重复行{len(repeats)}"
          f" | 隐形字符{invisible}")
    if repeats:
        print("  重复行示例:", list(repeats.items())[:3])


def main():
    files = sorted(STORE_DOCS.glob("*.pdf")) + sorted(STORE_DOCS.glob("*.docx"))
    for f in files:
        if f.suffix.lower() == ".pdf":
            inspect_pdf(f)
        else:
            print(f"\n== DOCX: {f.name} (python-docx 解析另测)")
    for f in sorted(DATA_DIR.glob("*.txt")):
        inspect_txt(f)
    print("\n体检完成。")


if __name__ == "__main__":
    sys.exit(main())
