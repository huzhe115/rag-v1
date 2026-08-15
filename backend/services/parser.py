"""Parse PDF/TXT/DOCX into Markdown-flavored text.

PDF 走 PyMuPDF：文字层抽取（带字号/坐标）→ 扫描页 OCR 兜底 → 双栏重排 →
标题推断（字号 + 行模式双兜底）→ 表格转 Markdown → 图内文字 OCR。
DOCX 走 python-docx（段落 + 表格按文档顺序）。
TXT 保留编码兼容（utf-8/gbk/gb2312），中文序号标题行加 "## " 前缀。

输出约定：标题行以 "## " 开头，表格为 Markdown 表，段落间以空行分隔——
供 chunker 按标题锚点切分、清洗层做行级统计。
"""
import re
import threading
from pathlib import Path

import cv2
import pymupdf as fitz
import numpy as np
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from rapidocr_onnxruntime import RapidOCR

SCAN_THRESHOLD = 30        # 每页文本层低于此字数 → 整页 OCR
HEADING_SIZE_MARGIN = 1.5  # 行字号比正文众数字号大此值 → 标题
HEADING_MAX_LEN = 40       # 标题行长度上限
OCR_DPI = 200
IMG_OCR_DPI = 150
IMG_OCR_MIN_SCORE = 0.6

# 中文序号标题行（"一、xxx"），与字号推断互为兜底；阿拉伯数字序号是列表项，不算标题
_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+[、.．]\s*\S{1,40}$")

_ocr = None
_ocr_lock = threading.Lock()


def _get_ocr() -> RapidOCR:
    """懒加载 OCR 引擎（初始化约 0.5s），线程安全。"""
    global _ocr
    if _ocr is None:
        with _ocr_lock:
            if _ocr is None:
                _ocr = RapidOCR()
    return _ocr


def parse_file(filepath: Path) -> str:
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(filepath)
    elif suffix == ".txt":
        return _parse_txt(filepath)
    elif suffix == ".docx":
        return _parse_docx(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}")


# ---------- PDF ----------

def _parse_pdf(path: Path) -> str:
    doc = fitz.open(str(path))
    try:
        parts = [p for p in (_parse_page(page) for page in doc) if p]
    finally:
        doc.close()
    if not parts:
        raise ValueError("PDF 无法提取内容")
    return "\n\n".join(parts)


def _parse_page(page: fitz.Page) -> str:
    if len(page.get_text("text").strip()) < SCAN_THRESHOLD:
        return _ocr_page(page)
    return _text_page(page)


def _pix_to_numpy(pix) -> np.ndarray:
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)


def _preprocess(img: np.ndarray) -> np.ndarray:
    """OCR 前图像预处理：灰度化 → 中值去噪 → CLAHE 对比度增强。

    不二值化：RapidOCR 的 DB 检测器依赖灰度梯度，二值化会丢抗锯齿信息；
    不做倾斜校正：检测框四点坐标对小幅倾斜鲁棒。
    """
    if img.ndim == 3:
        if img.shape[-1] == 4:
            img = img[:, :, :3]                       # RGBA → RGB
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)   # PyMuPDF pixmap 是 RGB
    img = cv2.medianBlur(img, 3)                     # 去扫描件椒盐噪点
    img = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(img)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)     # RapidOCR 需要 3 通道


def _ocr_page(page: fitz.Page) -> str:
    """扫描页：整页渲染 → OCR → 按坐标拼回阅读顺序。

    检测框四点不保证左上角在前，统一取 min(y)/min(x)；
    同一视觉行会被拆成多个框，按 y 聚类成行后行内按 x 拼接。
    """
    pix = page.get_pixmap(dpi=OCR_DPI)
    result, _ = _get_ocr()(_preprocess(_pix_to_numpy(pix)))
    if not result:
        return ""
    items = []
    for box, text, score in result:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append((min(ys), min(xs), text))

    items.sort(key=lambda i: (i[0], i[1]))
    lines: list[str] = []
    cur_y, cur_parts = None, []
    for y, x, text in items:
        if cur_y is None or y - cur_y < 15:  # 同一视觉行（200dpi 下 y 抖动几像素）
            if cur_y is None:
                cur_y = y
            cur_parts.append((x, text))
        else:
            lines.append("".join(t for _, t in sorted(cur_parts)))
            cur_y, cur_parts = y, [(x, text)]
    if cur_parts:
        lines.append("".join(t for _, t in sorted(cur_parts)))

    out = []
    for line in lines:
        if _HEADING_RE.match(line):  # OCR 页无字号信号，靠行模式补标题
            line = f"## {line}"
        out.append(line)
    return "\n".join(out)


def _text_page(page: fitz.Page) -> str:
    rows: list[tuple] = []  # (y, x, size, text)

    # 表格 bbox 内的文本行不重复进正文（find_tables 单独提取）
    table_boxes = [fitz.Rect(t.bbox) for t in page.find_tables()]

    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:  # 0=text
            continue
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if not text:
                continue
            bbox = fitz.Rect(line["bbox"])
            if any(bbox.intersects(tb) for tb in table_boxes):
                continue  # 表格内文字，交给表格提取
            sizes = [s["size"] for s in line["spans"] if s["text"].strip()]
            rows.append((bbox.y0, bbox.x0, max(sizes) if sizes else 0.0, text))

    # 表格按 y 位置插回行流
    for table in page.find_tables():
        md = _rows_to_markdown(table.extract())
        if md:
            rows.append((table.bbox[1], table.bbox[0], 0.0, md))

    # 图内文字：裁剪图片区域 OCR
    page_area = page.rect.width * page.rect.height
    for info in page.get_image_info():
        box = fitz.Rect(info["bbox"])
        if box.get_area() > page_area * 0.5:  # 跳过整页背景图
            continue
        img_text = _ocr_image(page, box)
        if img_text:
            rows.append((box.y0, box.x0, 0.0, f"（图内文字）\n{img_text}"))

    body_size = _median_size(rows)

    rows.sort(key=lambda r: (r[0], r[1]))
    rows = _split_columns(rows, page.rect.width)  # 必须在最终排序之后，否则被打回 y 序
    out: list[str] = []
    prev_y = None
    for y, x, size, text in rows:
        # 段落断点：行距 > 1.8×中位行距（block 切换不可靠，行距不会骗人）
        if out and prev_y is not None and (y - prev_y) > _para_gap(rows):
            out.append("")
        if _is_heading(text, size, body_size):
            out.append(f"## {text}")
        else:
            out.append(text)
        prev_y = y
    return "\n".join(out)


def _para_gap(rows: list) -> float:
    """相邻行 y 间距的中位数 × 1.8，超过即视为段落间隔。"""
    gaps = sorted(b[0] - a[0] for a, b in zip(rows, rows[1:]) if b[0] > a[0])
    return gaps[len(gaps) // 2] * 1.8 if gaps else 0.0


def _is_heading(text: str, size: float, body_size: float) -> bool:
    if len(text) > HEADING_MAX_LEN or text.startswith("|") or text.endswith("。"):
        return False
    if size and body_size and size >= body_size + HEADING_SIZE_MARGIN:
        return True
    return bool(_HEADING_RE.match(text))


def _median_size(rows: list) -> float:
    """中位字号作为正文基准（众数在小页面/表格页会失效）。"""
    sizes = sorted(r[2] for r in rows if r[2])
    return sizes[len(sizes) // 2] if sizes else 0.0


def _split_columns(rows: list, page_width: float) -> list:
    """双栏重排：行 x 起点的最大相邻间隙 > 12% 页宽且两侧行数相当 → 两栏，
    左栏整体在前、右栏在后，各自按 y 排序。

    # ponytail: 启发式天花板——跨栏大标题/图文混排会错位；
    # 语料升级到这类版面时换布局模型（MinerU/PP-Structure）。
    """
    xs = sorted(r[1] for r in rows)
    best_gap, split_x = 0.0, 0.0
    for a, b in zip(xs, xs[1:]):
        if b - a > best_gap:
            best_gap, split_x = b - a, (a + b) / 2
    if best_gap < page_width * 0.12:
        return rows
    left = [r for r in rows if r[1] < split_x]
    right = [r for r in rows if r[1] >= split_x]
    if not (0.3 < len(left) / len(rows) < 0.7):
        return rows  # 只有一侧有内容（如标题独占一行），单栏
    left.sort(key=lambda r: (r[0], r[1]))
    right.sort(key=lambda r: (r[0], r[1]))
    return left + right


def _ocr_image(page: fitz.Page, box: fitz.Rect) -> str:
    """图片区域 OCR；识别不出或置信度过低返回空串。"""
    try:
        pix = page.get_pixmap(clip=box, dpi=IMG_OCR_DPI)
    except Exception:
        return ""
    result, _ = _get_ocr()(_preprocess(_pix_to_numpy(pix)))
    texts = [t for _, t, s in (result or []) if s >= IMG_OCR_MIN_SCORE and t.strip()]
    return "\n".join(texts)


def _rows_to_markdown(rows) -> str:
    """表格数据 → Markdown 表；单行表多半是误检，放弃。"""
    rows = [
        [(c or "").replace("|", "\\|").replace("\n", " ").strip() for c in row]
        for row in rows
    ]
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = "| " + " | ".join(rows[0]) + " |"
    sep = "|" + "---|" * width
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
    return f"{header}\n{sep}\n{body}"


# ---------- DOCX ----------

def _parse_docx(path: Path) -> str:
    doc = Document(str(path))
    parts: list[str] = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            style = para.style.name or ""
            if "heading" in style.lower() or "标题" in style or _HEADING_RE.match(text):
                text = f"## {text}"
            parts.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            md = _rows_to_markdown([[c.text for c in row.cells] for row in table.rows])
            if md:
                parts.append(md)
    if not parts:
        raise ValueError("文档内容为空")
    return "\n\n".join(parts)


# ---------- TXT ----------

def _parse_txt(path: Path) -> str:
    for encoding in ("utf-8", "gbk", "gb2312"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ValueError("无法识别文件编码")

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if _HEADING_RE.match(line):
            line = f"## {line}"
        lines.append(line)
    if not any(l for l in lines):
        raise ValueError("文档内容为空")
    return "\n".join(lines)
