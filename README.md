# Multi-Agent MCP 电商客服系统

这是一个 **Multi-Agent MCP 电商客服系统**，基于 LangGraph 多 Agent 编排 + FastMCP 网关架构。

## 核心功能

- 多用户注册、登录、会话管理
- 电商客服聊天入口
- 后台知识库文档上传，支持 PDF / Markdown
- Qdrant 向量库 + BM25 sparse hybrid retrieval
- GraphRAG 关系图增强检索
- Parent-Child Chunking
- Cross-encoder / LLM / None 可选 reranker
- LangGraph 多 Agent 编排（Chat Router → 专用 Agent）
- **FastMCP Gateway 聚合架构**（port 9000），通过 stdio 挂载三个独立后端
  - `order_server`：订单 / 物流查询
  - `ticket_server`：创建 / 查询售后工单
  - `compliance_server`：客服风险检查
- LangChain MCP 工具桥接（`mcp_bridge`）
- Redis 短期记忆，Redis 不可用时自动回退 JSON 文件
- 检索质量评估框架（Retrieval eval）
- OpenTelemetry 链路追踪 + Jaeger 可视化
- Docker Compose 一键启动
## 当前架构

```text
User
  -> FastAPI Web UI (Gradio)
  -> LangGraph Supervisor / Router
     -> direct_chat
     -> order_query_agent -> MCP Bridge -> MCP Gateway (port 9000)
                                         -> order_server (order_query)
     -> ticket_agent      -> MCP Bridge -> MCP Gateway (port 9000)
                                         -> ticket_server (ticket_create / ticket_query)
     -> compliance_agent  -> MCP Bridge -> MCP Gateway (port 9000)
                                         -> compliance_server (risk_check)
     -> Knowledge RAG Agent
        -> Qdrant child chunks
        -> parent_store parent chunks
        -> graph_store entity/relation graph
        -> CRAG grading -> reranker -> answer synthesis

Redis
  -> short-term memory / ticket state

OpenTelemetry
  -> Jaeger
```

**MCP Gateway 内部细节：**

```text
Gateway (port 9000 / FastMCP)
  +- mount -- order_server (stdio subprocess)    -> order_query
  +- mount -- ticket_server (stdio subprocess)   -> ticket_create, ticket_query
  +- mount -- compliance_server (stdio subprocess) -> risk_check
```

App 通过 `mcp_bridge/langchain_adapter.py` 将 MCP Gateway 的工具转换为 LangChain 可调用的 Tool 对象，注入到对应的 Agent 节点中。

## 仓库结构

```text
.
+- docker-compose.yml              # app + gateway + Redis + Jaeger
+- requirements.txt
+- README.md
+- project/
   +- app.py                       # FastAPI Web UI 入口
   +- config.py                    # 配置中心
   +- utils.py                     # 通用工具函数
   +- document_chunker.py          # Parent-Child 文档分块
   +- core/
   |  +- rag_system.py             # RAG 检索与回答合成
   |  +- chat_interface.py         # 聊天逻辑
   |  +- document_manager.py       # 文档管理
   |  +- observability.py          # OpenTelemetry
   |  +- reranker.py               # Cross-encoder / LLM reranker
   |  +- user_store.py             # 用户存储
   +- db/
   |  +- vector_db_manager.py      # Qdrant 向量库管理
   |  +- parent_store_manager.py   # Parent chunk 存储
   +- ecommerce/
   |  +- tools.py                  # 订单/工单/风险 MCP 工具实现
   |  +- tickets.py                # Redis / JSON fallback 工单存储
   |  +- compliance.py             # 风险审查逻辑
   +- gateway/
   |  +- server.py                 # FastMCP Gateway（聚合三个后端）
   +- mcp_bridge/
   |  +- langchain_adapter.py      # LangChain MCP 工具适配器
   +- memory/
   |  +- short_term.py             # Redis / JSON fallback 短期记忆
   |  +- working_memory.py         # 工作记忆
   +- graph_rag/
   |  +- store.py                  # JSON-backed GraphRAG 图谱存储与检索
   +- rag_agent/
   |  +- graph.py                  # LangGraph 图定义
   |  +- graph_state.py            # State 定义
   |  +- nodes.py                  # 各 Agent 节点逻辑
   |  +- edges.py                  # 条件路由
   |  +- mcp_agents.py             # MCP 专用 Agent 封装
   |  +- tools.py                  # 本地工具函数
   |  +- schemas.py                # Pydantic 模型
   |  +- prompts.py                # 提示词模板
   +- ui/
   |  +- fastapi_ui.py             # Gradio / FastAPI Web UI
   +- mcp_order_server.py          # 独立订单 MCP 服务器（stdio）
   +- mcp_ticket_server.py         # 独立工单 MCP 服务器（stdio）
   +- mcp_compliance_server.py     # 独立风控 MCP 服务器（stdio）
   +- mcp_fastmcp_server.py        # 单体 MCP 服务器（全部工具，可选）
   +- eval_retrieval.py            # 检索质量评估脚本
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
SPARSE_MODEL=none
RERANKER_TYPE=none
```

如果你本机首次运行，为了降低模型下载和启动压力，可以先设置：

```env
RERANKER_TYPE=none
```

## 推荐运行方式：Docker Compose

Docker Compose 会启动：

- `app`：FastAPI Web UI，端口 `7860`
- `gateway`：FastMCP Gateway（聚合订单/工单/风控服务），端口 `9000`
- `redis`：短期记忆和工单状态
- `jaeger`：OpenTelemetry 链路追踪 UI

启动：

```bash
docker compose up --build
```

Docker Compose 中的 app 容器会通过 `http://host.docker.internal:11434` 访问宿主机 Ollama。Windows 上如果容器连不上 Ollama，需要让 Ollama 监听所有网卡后重启 Ollama：

```powershell
setx OLLAMA_HOST 0.0.0.0:11434
```

访问：

```text
应用页面:   http://127.0.0.1:7860
MCP Gateway: http://127.0.0.1:9000/mcp
Jaeger:     http://127.0.0.1:16686
```

停止：

```bash
docker compose down
```

## 本地开发运行

### 1. 创建并激活虚拟环境

推荐使用 Python 3.12 + uv（或 pip）：

```bash
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

### 3. 启动 MCP Gateway

新开一个终端，启动 Gateway（会通过 stdio 自动拉起三个后端服务器）：

```bash
cd project
python gateway/server.py
```

默认地址：

```text
http://127.0.0.1:9000/mcp
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
- GraphRAG 图谱索引：抽取电商领域实体和共现关系，例如"七天无理由""退货政策""耳机商品""保修政策"等，用于回答政策适用关系、商品规则关联、售后条件组合类问题。

可以测试这些问题：

```text
你好
```

走普通聊天。

```text
帮我查订单 ORD-20260510-001 到哪了
```

走 `order_query_agent`，通过 MCP Gateway 查询模拟订单状态。

```text
我要退款，商家一直不处理
```

走 `ticket_agent`，通过 MCP Gateway 创建售后工单。

```text
查询工单 TK-20260510-ABC123
```

走 `ticket_agent`，通过 MCP Gateway 查询工单。

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
| `MCP_SERVER_URL` | MCP 工具服务地址 | `http://127.0.0.1:9000/mcp` |
| `MCP_GATEWAY_URL` | MCP Gateway 地址（同 MCP_SERVER_URL） | `http://127.0.0.1:9000/mcp` |
| `MCP_TRANSPORT` | MCP 传输协议（http / stdio / sse） | `http` |
| `MCP_USE_LANGCHAIN_TOOLS` | 是否使用 LangChain MCP 工具适配 | `true` |
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
- MCP Gateway 调用
- MCP server 内部调用

本地开发时如需启用：

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=multi-agent-mcp-app
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318/v1/traces
```

## 检索质量评估

项目内置了检索质量评估脚本 `project/eval_retrieval.py`，支持对 RAG 管道的检索质量进行评估。评估数据格式见 `project/eval_questions.example.jsonl`。

```bash
cd project
python eval_retrieval.py
```

## 当前边界

- **MCP Gateway**：当前基于 FastMCP `create_proxy` 通过 stdio 挂载三个独立后端服务器，对外暴露 `tools/list` 和 `tools/call` JSON-RPC 端点。后续可升级为完整的 MCP 协议实现。
- **订单数据**：模拟数据，不连接真实电商订单系统。
- **工单数据**：使用 Redis，Redis 不可用时回退 JSON 文件。
- **GraphRAG**：当前使用轻量 JSON 图谱存储，适合本地学习和小型知识库；生产环境可以替换为 Neo4j / NebulaGraph 等图数据库。
- **单体 MCP 服务器**：`mcp_fastmcp_server.py` 将全部工具打包在一个 FastMCP 实例中，可选替代 Gateway 架构用于简化调试。

## License

本仓库使用 [MIT License](LICENSE)。
