# Multi-Agent MCP 电商客服系统

这是一个 **Multi-Agent MCP 电商客服系统**。

当前版本的目标是构造一个可继续扩展的电商智能客服项目骨架。

## 核心功能

- 多用户注册、登录、会话管理
- 电商客服聊天入口
- 后台知识库文档上传，支持 PDF / Markdown
- Qdrant 向量库 + BM25 sparse hybrid retrieval
- GraphRAG 关系图增强检索
- Parent-Child Chunking
- Cross-encoder / LLM / None 可选 reranker
- LangGraph 多 Agent 编排
- MCP 工具服务
  - `order_query`：模拟订单 / 物流查询
  - `ticket_create`：创建售后工单
  - `ticket_query`：查询售后工单
  - `risk_check`：客服风险检查
- Redis 短期记忆，Redis 不可用时自动回退 JSON 文件
- OpenTelemetry 链路追踪
- Jaeger 可视化追踪
- Docker Compose 一键启动

## 当前架构

```text
User
  -> FastAPI Web UI
  -> LangGraph Supervisor / Router
     -> general_chat
     -> order_query_agent
        -> MCP client -> MCP server -> order_query
     -> ticket_agent
        -> MCP client -> MCP server -> ticket_create / ticket_query
     -> compliance_agent
        -> MCP client -> MCP server -> risk_check
     -> Knowledge RAG Agent
        -> Qdrant child chunks
        -> parent_store parent chunks
        -> graph_store entity/relation graph
        -> reranker / CRAG grading / answer synthesis

Redis
  -> short-term memory / ticket state

OpenTelemetry
  -> Jaeger
```

## 仓库结构

```text
.
├─ docker-compose.yml              # app + MCP server + Redis + Jaeger
├─ requirements.txt
├─ README.md
└─ project/
   ├─ app.py                       # FastAPI Web UI 入口
   ├─ mcp_server_app.py            # 独立 MCP 工具服务入口
   ├─ config.py                    # 配置中心
   ├─ document_chunker.py
   ├─ core/
   │  ├─ rag_system.py
   │  ├─ chat_interface.py
   │  ├─ document_manager.py
   │  ├─ observability.py          # OpenTelemetry
   │  └─ user_store.py
   ├─ db/
   │  ├─ vector_db_manager.py      # Qdrant
   │  └─ parent_store_manager.py
   ├─ ecommerce/
   │  ├─ tools.py                  # 电商 MCP 工具实现
   │  ├─ tickets.py                # Redis / JSON fallback 工单存储
   │  └─ compliance.py
   ├─ mcp/
   │  ├─ client.py
   │  └─ registry.py
   ├─ memory/
   │  ├─ short_term.py
   │  └─ working_memory.py
   ├─ graph_rag/
   │  └─ store.py                  # JSON-backed GraphRAG 图谱存储与检索
   ├─ rag_agent/
   │  ├─ graph.py
   │  ├─ nodes.py
   │  ├─ edges.py
   │  ├─ tools.py
   │  └─ prompts.py
   └─ ui/
      └─ fastapi_ui.py
```

## 运行前准备

### 1. 准备 LLM 接口

项目使用 OpenAI-compatible Chat API。你需要准备：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

默认配置偏向 DashScope/OpenAI-compatible：

```text
LLM_MODEL=qwen-max-0919
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 2. 准备 Ollama Embedding

当前向量检索使用 Ollama embedding，默认模型是 `nomic-embed-text`。

```bash
ollama serve
ollama pull nomic-embed-text
```

Docker Compose 中默认使用：

```text
OLLAMA_HOST=http://host.docker.internal:11434
```

如果 Ollama 不在宿主机运行，请在 `project/.env` 或 Compose 环境变量中修改。

### 3. 创建环境变量文件

Windows PowerShell:

```powershell
Copy-Item project\.env.example project\.env
```

macOS / Linux:

```bash
cp project/.env.example project/.env
```

然后至少填写：

```env
LLM_MODEL=qwen-max-0919
LLM_TEMPERATURE=0
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=your-api-key
DENSE_MODEL=nomic-embed-text
SPARSE_MODEL=Qdrant/bm25
RERANKER_TYPE=cross_encoder
```

如果你本机首次运行，为了降低模型下载和启动压力，可以先设置：

```env
RERANKER_TYPE=none
```

## 推荐运行方式：Docker Compose

Docker Compose 会启动：

- `app`：FastAPI Web UI，端口 `7860`
- `mcp-server`：MCP 工具服务，端口 `8765`
- `redis`：短期记忆和工单状态
- `jaeger`：OpenTelemetry 链路追踪 UI

启动：

```bash
docker compose up --build
```

访问：

```text
应用页面: http://127.0.0.1:7860
MCP 工具: http://127.0.0.1:8765/tools
Jaeger:   http://127.0.0.1:16686
```

停止：

```bash
docker compose down
```

如果也想删除 Redis / Qdrant / app 数据卷：

```bash
docker compose down -v
```

## 本地开发运行

推荐 Python 3.12。

### 1. 创建虚拟环境

使用 `uv`：

```bash
uv python install 3.12
uv venv --python 3.12 .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
source .venv/bin/activate
```

安装依赖：

```bash
uv pip install --index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

或使用 pip：

```bash
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```

### 2. 启动 Redis

Redis 是推荐项，不是强依赖。没有 Redis 时，系统会回退到 `project/data/short_term_memory.json`。

如果本机有 Docker，可以只启动 Redis：

```bash
docker run --rm -p 6379:6379 redis:7-alpine
```

### 3. 启动 MCP 工具服务

新开一个终端：

```bash
cd project
python mcp_server_app.py
```

默认地址：

```text
http://127.0.0.1:8765/tools
```

### 4. 启动 Web 应用

再开一个终端：

```bash
cd project
python app.py
```

默认地址：

```text
http://127.0.0.1:7860
```

## 使用流程

1. 打开 `http://127.0.0.1:7860`
2. 注册并登录
3. 进入 Documents 页面上传电商知识库文档，例如：
   - 退换货政策
   - 退款规则
   - 物流时效说明
   - 保修政策
   - 商品说明书
   - 活动规则 FAQ
4. 回到聊天页面提问

上传文档时，系统会同时建立两类索引：

- Qdrant 向量索引：用于语义检索具体片段。
- GraphRAG 图谱索引：抽取电商领域实体和共现关系，例如“七天无理由”“退货政策”“耳机商品”“保修政策”等，用于回答政策适用关系、商品规则关联、售后条件组合类问题。

可以测试这些问题：

```text
你好
```

走普通聊天。

```text
帮我查订单 ORD-20260510-001 到哪了
```

走 `order_query_agent`，通过 MCP 工具查询模拟订单状态。

```text
我要退款，商家一直不处理
```

走 `ticket_agent`，通过 MCP 工具创建售后工单。

```text
查询工单 TK-20260510-ABC123
```

走 `ticket_agent`，通过 MCP 工具查询工单。

```text
七天无理由退货规则是什么？
```

如果知识库中有相关文档，会走 Knowledge RAG Agent，从 Qdrant 和 GraphRAG 图谱共同检索证据后回答。

```text
耳机商品和七天无理由退货有什么关系？
```

这类关系型问题会优先受益于 GraphRAG 的实体和关系证据。

## 关键配置

配置优先级：

1. 进程环境变量
2. `project/.env`
3. `project/config.py` 默认值

常用配置：

| 配置 | 说明 | 默认值 |
|---|---|---|
| `LLM_MODEL` | Chat 模型名称 | `qwen-max-0919` |
| `LLM_BASE_URL` | OpenAI-compatible API 地址 | DashScope compatible endpoint |
| `LLM_API_KEY` | LLM API Key | 空 |
| `DENSE_MODEL` | Ollama embedding 模型 | `nomic-embed-text` |
| `SPARSE_MODEL` | Sparse retrieval 模型 | `Qdrant/bm25` |
| `RERANKER_TYPE` | `cross_encoder` / `llm` / `none` | `cross_encoder` |
| `GRAPH_RAG_ENABLED` | 是否启用 GraphRAG 图谱检索 | `true` |
| `GRAPH_RAG_MAX_RESULTS` | GraphRAG 最多返回的证据数量 | `8` |
| `REDIS_URL` | Redis 地址 | `redis://localhost:6379/0` |
| `MCP_SERVER_URL` | MCP 工具服务地址 | `http://127.0.0.1:8765/mcp` |
| `OTEL_ENABLED` | 是否启用 OpenTelemetry | `false` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP HTTP endpoint | 空 |
| `APP_HOST` | Web 服务监听地址 | `127.0.0.1` |
| `APP_PORT` | Web 服务端口 | `7860` |

## 数据目录

运行后会生成：

```text
data/                       # 用户、会话、知识库文档等运行数据
qdrant_db/                  # 本地 Qdrant 数据
project/data/               # Redis 不可用时的短期记忆 fallback
data/user_data/<user>/graph_store/   # 每个用户的 GraphRAG 图谱
```

这些目录已在 `.gitignore` 中忽略。

## OpenTelemetry / Jaeger

Docker Compose 默认启用 OpenTelemetry，并导出到 Jaeger：

```text
http://127.0.0.1:16686
```

你可以在 Jaeger 中查看：

- FastAPI 请求
- 聊天流式响应 span
- MCP client 调用
- MCP server JSON-RPC 调用

本地开发时如需启用：

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=multi-agent-mcp-app
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

## 当前边界

- MCP 工具服务当前是项目内 JSON-RPC 风格工具服务，已提供 `tools/list` 和 `tools/call`，后续可以继续升级为更完整的 MCP 协议实现。
- 订单数据是模拟数据，不连接真实电商订单系统。
- 工单数据使用 Redis，Redis 不可用时回退 JSON 文件。
- GraphRAG 当前使用轻量 JSON 图谱存储，适合本地学习和小型知识库；生产环境可以继续替换为 Neo4j / NebulaGraph 等图数据库。
- 文档上传页面目前保留原 UI，定位为知识库管理入口。

## License

本仓库使用 [MIT License](LICENSE)。
