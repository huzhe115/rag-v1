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

# Upload limits
MAX_UPLOAD_MB = 50

# Ensure store dirs exist
STORE_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
