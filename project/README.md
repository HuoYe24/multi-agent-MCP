# Project Implementation Notes

`project/` contains the runnable Python application for the Multi-Agent MCP e-commerce customer-service system.

## Entry Points

| File | Purpose |
|---|---|
| `app.py` | Starts the FastAPI Web UI on `APP_HOST:APP_PORT` |
| `gateway/server.py` | Starts the MCP Gateway on port `9000`, aggregating order / ticket / compliance backends |
| `mcp_order_server.py` | Standalone order MCP server (port `8765`, normally spawned by Gateway) |
| `mcp_ticket_server.py` | Standalone ticket MCP server (port `8766`, normally spawned by Gateway) |
| `mcp_compliance_server.py` | Standalone compliance MCP server (port `8767`, normally spawned by Gateway) |
| `config.py` | Central environment-driven configuration |

## Main Runtime Flow

```text
FastAPI UI
  -> ChatInterface
  -> RAGSystem
  -> LangGraph
     -> direct_chat
     -> order_query_agent
     -> ticket_agent
     -> compliance_agent
     -> Knowledge RAG Agent
        -> search_child_chunks
        -> search_knowledge_graph
        -> retrieve_parent_chunks
        -> grade / compress / answer
```

## Key Modules

| Path | Purpose |
|---|---|
| `core/rag_system.py` | Creates Qdrant, parent store, GraphRAG store, MCP client (via Gateway), and LangGraph |
| `gateway/server.py` | MCP Gateway aggregating three backend services via `create_proxy` + `mount` |
| `core/document_manager.py` | Converts/uploads documents, writes Qdrant child chunks, parent chunks, and GraphRAG graph |
| `db/vector_db_manager.py` | Local Qdrant hybrid retrieval |
| `db/parent_store_manager.py` | JSON parent-chunk storage |
| `graph_rag/store.py` | Lightweight JSON-backed GraphRAG store and search |
| `rag_agent/tools.py` | LangChain tools: vector search, graph search, parent retrieval |
| `rag_agent/nodes.py` | Router nodes, e-commerce agents, and RAG subgraph nodes |
| `ecommerce/tools.py` | MCP tool implementations for order, ticket, risk check |
| `memory/short_term.py` | Redis short-term memory with JSON fallback |
| `core/observability.py` | OpenTelemetry setup and FastAPI instrumentation |

## GraphRAG

GraphRAG is enabled by default.

During document upload:

1. PDF / Markdown is converted into Markdown.
2. The document is split into parent and child chunks.
3. Child chunks are stored in Qdrant.
4. Parent chunks are stored as JSON.
5. `GraphRAGStore.index_parent_chunks()` extracts e-commerce entities and co-occurrence relations into `graph.json`.

During question answering:

1. The RAG agent can call `search_child_chunks` for vector evidence.
2. For relationship-heavy policy/product questions, it can call `search_knowledge_graph`.
3. It can then retrieve full parent chunks with `retrieve_parent_chunks`.

The current GraphRAG implementation is intentionally lightweight and local:

- Storage: JSON file
- Scope: per user
- Best for: product-policy, return/refund/warranty/shipping relationships
- Not intended as a replacement for Qdrant

## Local Run

From the repository root:

```bash
cp project/.env.example project/.env
```

Fill in at least `LLM_API_KEY`.

Install dependencies:

```bash
uv venv --python 3.12 .venv
uv pip install -r requirements.txt
```

Start MCP Gateway (spawns order / ticket / compliance backends automatically):

```bash
cd project
python gateway/server.py
```

Start app in another terminal:

```bash
cd project
python app.py
```

Open:

```text
http://127.0.0.1:7860
```

## Docker Compose

From the repository root:

```bash
docker compose up --build
```

Services:

```text
App:     http://127.0.0.1:7860
Gateway: http://127.0.0.1:9000/mcp
Jaeger:  http://127.0.0.1:16686
```

## Important Configuration

| Variable | Default |
|---|---|
| `GRAPH_RAG_ENABLED` | `true` |
| `GRAPH_RAG_MAX_RESULTS` | `8` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `MCP_SERVER_URL` | `http://127.0.0.1:9000/mcp` (Gateway address) |
| `OTEL_ENABLED` | `false` |
| `RERANKER_TYPE` | `cross_encoder` |

For first local runs, `RERANKER_TYPE=none` is often faster and avoids downloading a cross-encoder model.
