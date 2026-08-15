"""Text chunking: heading-anchored parent chunks + fine children."""
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CHUNK_SEPARATORS, PARENT_SIZE, PARENT_OVERLAP, CHILD_SIZE, CHILD_OVERLAP

_HEADING_LINE = re.compile(r"^##\s+")


def _make_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        separators=CHUNK_SEPARATORS,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        keep_separator=False,
    )


def split_parents(text: str) -> list[str]:
    """Coarse chunks (~900 chars) — the unit returned to the LLM.

    "## " 标题行先切章节，章节内再按原尺寸递归切；
    标题只挂在章节首块（每块都挂会让 BM25 词频虚高）。
    无标题文本行为与旧版一致。
    """
    sections: list[tuple[str, str]] = []
    cur_heading, buf = "", []
    for line in text.split("\n"):
        if _HEADING_LINE.match(line):
            if buf or cur_heading:
                sections.append((cur_heading, "\n".join(buf)))
            cur_heading, buf = line.strip(), []
        else:
            buf.append(line)
    if buf or cur_heading:
        sections.append((cur_heading, "\n".join(buf)))

    splitter = _make_splitter(PARENT_SIZE, PARENT_OVERLAP)
    chunks: list[str] = []
    current = ""
    for heading, body in sections:
        piece = (f"{heading}\n{body}" if heading else body).strip()
        if not piece:
            continue
        if len(piece) <= PARENT_SIZE:
            # 小节贪心合并回一块，避免父块碎片化
            if current and len(current) + len(piece) + 2 <= PARENT_SIZE:
                current = f"{current}\n\n{piece}"
            else:
                if current:
                    chunks.append(current)
                current = piece
        else:
            # 大节递归切分，标题自然落在首块
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(splitter.split_text(piece))
    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def split_children(parent: str) -> list[str]:
    """Fine chunks (~250 chars) — the unit embedded for vector search."""
    splitter = _make_splitter(CHILD_SIZE, CHILD_OVERLAP)
    docs = splitter.create_documents([parent])
    return [d.page_content for d in docs]
