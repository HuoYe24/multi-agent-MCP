import os

# --- Directory Configuration ---
_PROJECT_DIR = os.path.dirname(__file__)
_BASE_DIR = os.path.dirname(_PROJECT_DIR)

MARKDOWN_DIR = os.path.join(_BASE_DIR, "data", "_legacy_default", "markdown_docs")
PARENT_STORE_PATH = os.path.join(_BASE_DIR, "data", "_legacy_default", "parent_store")
QDRANT_DB_PATH = os.path.join(_BASE_DIR, "qdrant_db")

# --- Qdrant Configuration ---
CHILD_COLLECTION = "document_child_chunks"
SPARSE_VECTOR_NAME = "sparse"

# --- Model Configuration ---
DENSE_MODEL = os.environ.get("DENSE_MODEL", "nomic-embed-text")
SPARSE_MODEL = os.environ.get("SPARSE_MODEL", "Qdrant/bm25")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-max-0919")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0"))

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# --- Agent Configuration ---
MAX_TOOL_CALLS = 8
MAX_ITERATIONS = 10
CRAG_MAX_RETRIES = 2
GRAPH_RECURSION_LIMIT = 50
BASE_TOKEN_THRESHOLD = 2000
TOKEN_GROWTH_FACTOR = 0.9

# --- Text Splitter Configuration ---
CHILD_CHUNK_SIZE = 500
CHILD_CHUNK_OVERLAP = 100
MIN_PARENT_SIZE = 2000
MAX_PARENT_SIZE = 4000
HEADERS_TO_SPLIT_ON = [
    ("#", "H1"),
    ("##", "H2"),
    ("###", "H3")
]

# --- Reranker Configuration ---
RERANKER_TYPE = os.environ.get("RERANKER_TYPE", "cross_encoder").strip().lower()  # Options: "llm", "cross_encoder", "none"
RERANKER_ENABLED = RERANKER_TYPE in {"llm", "cross_encoder"}
CROSS_ENCODER_RERANKER_MODEL = os.environ.get("CROSS_ENCODER_RERANKER_MODEL", "BAAI/bge-reranker-base")
INITIAL_SEARCH_TOP_K = 10  # Initial retrieval top-K
RERANKER_TOP_M = 5         # Rerank result top-M (M <= K)
FINAL_OUTPUT_TOP_N = 5     # Final output top-N unique parent chunks

# --- Redis / Short-term Memory ---
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
SHORT_TERM_MEMORY_TTL_SECONDS = int(os.environ.get("SHORT_TERM_MEMORY_TTL_SECONDS", "1800"))
SHORT_TERM_MEMORY_MAX_TURNS = int(os.environ.get("SHORT_TERM_MEMORY_MAX_TURNS", "20"))
SHORT_TERM_MEMORY_FALLBACK_PATH = os.environ.get(
    "SHORT_TERM_MEMORY_FALLBACK_PATH",
    os.path.join(_PROJECT_DIR, "data", "short_term_memory.json"),
)

# --- MCP Tool Server ---
MCP_SERVER_HOST = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
MCP_SERVER_PORT = int(os.environ.get("MCP_SERVER_PORT", "8765"))
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8765/mcp")
MCP_CLIENT_TIMEOUT_SECONDS = float(os.environ.get("MCP_CLIENT_TIMEOUT_SECONDS", "3"))

# --- OpenTelemetry Observability ---
OTEL_ENABLED = os.environ.get("OTEL_ENABLED", "false").lower() == "true"
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "multi-agent-mcp-app")
OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
OTEL_CONSOLE_EXPORT = os.environ.get("OTEL_CONSOLE_EXPORT", "false").lower() == "true"

# --- E-commerce Customer Service ---
ECOMMERCE_DEFAULT_STORE_NAME = os.environ.get("ECOMMERCE_DEFAULT_STORE_NAME", "Demo Store")
