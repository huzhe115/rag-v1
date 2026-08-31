"""RAG-v1 configuration. All paths, models, and knobs in one place."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STORE_DIR = BASE_DIR / "store"
CHROMA_DIR = STORE_DIR / "chroma"
DOCS_DIR = STORE_DIR / "documents"
DB_PATH = STORE_DIR / "app.db"
BM25_CACHE = STORE_DIR / "bm25_cache.pkl"  # BM25 索引持久化缓存，启动直接加载免重建

# LLM
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("CHAT_MODEL", "deepseek-chat")

# Embedding
EMBED_MODEL = "BAAI/bge-small-zh-v1.5"
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

# Reranker
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# Chunking (Chinese-friendly separators)
CHUNK_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "，", "、", " ", ""]
PARENT_SIZE = 900
PARENT_OVERLAP = 100
CHILD_SIZE = 250
CHILD_OVERLAP = 30

# Retrieval knobs
VECTOR_K = 8
BM25_K = 8
RRF_K = 60
RERANK_TOP_N = 5
HISTORY_TURNS = 3  # how many recent message pairs go into the prompt

# Context window & compaction（借鉴 Claude Code auto-compact：总上下文超窗口 65% 触发）
CONTEXT_WINDOW_TOKENS = int(os.getenv("CONTEXT_WINDOW_TOKENS", "64000"))  # deepseek-chat 上下文窗口
COMPACT_THRESHOLD_PCT = float(os.getenv("COMPACT_THRESHOLD_PCT", "65"))
SUMMARY_MAX_TOKENS = 800  # 压缩摘要长度上限

# Web search fallback (Tavily) — 本地检索耗尽时的联网兜底
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")  # 不填则禁用联网兜底
TAVILY_MAX_RESULTS = int(os.getenv("TAVILY_MAX_RESULTS", "3"))
TAVILY_SCORE_THRESHOLD = float(os.getenv("TAVILY_SCORE_THRESHOLD", "0.5"))  # 低于此相关分的结果丢弃

# Upload limits
MAX_UPLOAD_MB = 50

# Ensure store dirs exist
STORE_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
