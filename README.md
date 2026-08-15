# RAG-v1

本地 RAG 知识库问答系统：从零实现的混合检索 + 复杂文档处理管线。上传 PDF/DOCX/TXT，向它提问，答案带资料引用。

## 特性

- **混合检索**：向量检索（子块 embedding）+ BM25 关键词检索（jieba 分词）→ RRF 融合 → cross-encoder 精排
- **复杂文档解析**：文字层 PDF（含表格转 Markdown、双栏重排、标题推断）、扫描件 OCR 兜底、图内文字 OCR、DOCX 表格提取
- **规则清洗**：页眉页脚/页码剔除、段落去重、乱码检测——纯规则、确定性、原文零改写
- **查询自适应**：LangGraph 检索分级循环，检索不足时自动改写查询重试
- **自建评测设施**：100 题评测集 + 四档消融（Hit@k / MRR），改造前后可量化对比

## 系统架构

```
┌─ 数据进库 ─────────────────────────────────────────────────┐
│  PDF ─ PyMuPDF 文字层 → 扫描页检测 → RapidOCR 兜底        │
│        ├─ 表格 → Markdown     ├─ 双栏坐标聚类重排          │
│        └─ 标题字号/行模式推断 → "## " 标注                 │
│  DOCX ─ python-docx（段落 + 表格）                          │
│  TXT  ─ utf-8/gbk 编码兼容                                  │
│      ↓                                                      │
│  清洗（cleaner.py）：页眉页脚/页码剔除 → 段落去重 → 乱码检测│
│      ↓                                                      │
│  标题锚点切块：父块 900 字（LLM 上下文/BM25）+ 子块 250 字  │
│  （向量检索），小节贪心合并防碎片化                          │
│      ↓                                                      │
│  ChromaDB（向量）+ 内存 BM25（关键词）                      │
└────────────────────────────────────────────────────────────┘
                          ↓
┌─ 检索问答 ─────────────────────────────────────────────────┐
│  查询 → 向量检索(子块,k=8) + BM25(父块,k=8)                │
│       → RRF 融合 Top-20 → bge-reranker-v2-m3 精排 Top-5    │
│       → LangGraph 分级：资料不足则改写查询重试              │
│       → DeepSeek 流式生成（带 [1][2] 资料引用）            │
└────────────────────────────────────────────────────────────┘
```

## 评测结果（自建 100 题评测集）

四档消融（78 题口径，父块命中 Hit@k）：

| 方法 | Hit@1 | Hit@3 | Hit@5 | MRR@5 |
|---|---|---|---|---|
| 仅向量 | 78.2% | 93.6% | 100% | 0.864 |
| 仅 BM25 | 60.3% | 73.1% | 97.4% | 0.722 |
| 融合 (RRF) | 88.5% | 100% | 100% | 0.942 |
| **融合 + rerank** | **96.2%** | **100%** | **100%** | **0.981** |

复杂文档评测（22 题：表格 / 双栏 / 扫描件 PDF）：Hit@1 **95.5%**，Hit@3 100%。
全套 100 题：Hit@1 95.0%，Hit@5 99.0%。

失败案例（2 题）已归因：同文档多章节同义词干扰、OCR 噪声块挤占候选——详见 `backend/eval.py` 运行输出。

## 快速启动

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 填入 DEEPSEEK_API_KEY
uvicorn main:app --port 8000
```

> Python 3.13 注意：`rapidocr_onnxruntime` 会解析到 1.2.3（上游 1.3.18+ 声明 `<3.13`），
> 这是正常现象。PyTorch 需装 CUDA 版，否则 reranker 评测慢 4 倍。

### 2. 前端（开发模式）

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### 3. 单服务模式（演示/部署）

```bash
cd frontend && npm run build
cd ../backend && uvicorn main:app --port 8000
# 访问 http://localhost:8000，API 文档 /docs
```

### 4. 导入文档与评测

```bash
# 把文档放进 data/ 后批量导入（SHA256 去重，可重复执行）
cd backend && python import_data.py

# 语料体检（文本层覆盖率/表格数/扫描页占比）
python inspect_data.py

# 四档消融评测（GPU 约 3 分钟）
python eval.py
```

复杂 PDF 测试样本与生成脚本见 `testsamples/`（表格+跨页表、3 页双栏、4 页扫描件）。

## 项目结构

```
rag-v1/
├── backend/
│   ├── main.py              # FastAPI 入口（含前端静态托管）
│   ├── config.py            # 模型/切块/检索/上传限制，全部可调
│   ├── routers/             # upload.py（上传/列表/删除）, chat.py（SSE 问答）
│   ├── services/
│   │   ├── parser.py        # PyMuPDF + RapidOCR + python-docx 解析
│   │   ├── cleaner.py       # 规则清洗（页眉页脚/去重/乱码）
│   │   ├── chunker.py       # 标题锚点父子切块
│   │   ├── indexer.py       # ChromaDB + BM25 索引（单例）
│   │   ├── retriever.py     # 混合检索 + RRF 融合
│   │   ├── reranker.py      # cross-encoder 精排
│   │   ├── graph.py         # LangGraph 检索分级/查询改写
│   │   └── llm.py           # DeepSeek 流式生成
│   ├── models/database.py   # SQLite（会话/消息/文档元数据）
│   ├── eval.py              # 四档消融评测
│   ├── eval_qa.json         # 100 题评测集（问题+答案摘录+所属文档）
│   └── import_data.py       # 批量导入
├── data/                    # 语料文档
├── testsamples/             # 复杂 PDF 测试样本 + 生成脚本
├── frontend/                # React 19 + Vite + TS
└── store/                   # ChromaDB + SQLite + 原始文档（运行时生成）
```

## API

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/upload` | 上传文件（SHA256 去重，50MB 上限，支持批量） |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| POST | `/api/chat/{session_id}` | SSE 流式问答（先返回 sources 再流式 delta） |
| GET | `/api/sessions` | 会话列表 |
| POST | `/api/sessions` | 新建会话 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/sessions/{id}/messages` | 历史消息 |

## 已知局限

- BM25 索引在文档增删时全量重建（O(N)，万级文档内可接受）
- 复杂合并单元格/跨页表格的还原仍会出错（业界 MinerU 同样存在）
- 双栏重排为坐标聚类启发式，跨栏大标题/图文混排会错位
- OCR 引擎受 Python 3.13 限制锁定 1.2.3（老模型），数字识别偶有误差
- 索引为单进程内存/本地存储，未做并发与分布式扩展
