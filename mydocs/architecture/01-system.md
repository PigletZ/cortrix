# 系统总览与生命周期

Archify 重绘：[01-system](../diagrams/archify/01-system/01-system.html) · [02-bootstrap](../diagrams/archify/02-bootstrap/02-bootstrap.html)

## 定位和核心实体

Cortrix 是本地优先的语义存储系统。Namespace 是逻辑集合边界，Document 保存来源身份和文档状态，Parent 保存较大上下文，Child/Block 是召回单元；向量索引提供语义近邻，SQLite FTS5 提供词项召回。Memory 是独立业务能力，不等价于聊天进程中的 session history。

项目并非一个 Python RAG 包：主服务由 C++17 编译为 `cortrix-server`，Python 和 React 工程围绕 HTTP API 集成。核心实现聚合在 CMake 静态库 `cortrix_core` 中；源码头文件主要位于 `include/cortrix/`，实现位于 `src/`。

[系统图](../diagrams/README.md#01-系统与进程边界) · [启动图](../diagrams/02-bootstrap.mmd)

## 进程与网络边界

| 部件 | 入口 | 输入 | 输出 / 外部依赖 |
|---|---|---|---|
| Core | `src/main.cpp` → `server::RunServer` | HTTP、文件、YAML/env/CLI | JSON、SSE 代理、SQLite、blob、WAL、ONNX、可选外部 LLM |
| Web | `web/src/main.tsx`、`routes.tsx` | 浏览器事件 / 路由 | API JSON、multipart 上传、聊天流 |
| MCP | `cortrix-mcp/src/cortrix_mcp/mcp_server.py` | 本地 stdio MCP 工具调用 | 独立 httpx 请求到 Core；不是经 Python SDK 转发 |
| SDK | `sdk/python/cortrix/_client.py`、`_async_client.py` | Python typed resources | HTTP 请求与 typed result / exceptions |
| Agent | `cortrix-agent/main.py` | FastAPI chat、sessions、config | SDK 检索 + 外部 LLM stream + SSE；默认端口配置 8001 |
| Skills | `cortrix-skills/src/cortrix_skills/toolkit.py` | 框架 tool invocation | SDK；OpenAI/Claude/LangChain 适配 |
| PostgreSQL 扩展 | `sql-extensions/pgcortrix/` | PostgreSQL 扩展接口 | 独立集成工程，不能当作 Core 的底层数据库 |

Core 默认 HTTP 端口 8420。Compose Quick Start 只发布宿主机 loopback，单个 core service 使用 `/data` volume，真实 CPU embedding/reranker 开启，外部 LLM 和内置 Agent 关闭。因此“仓库含 Agent”不表示默认 Compose 已运行 Agent。

## 启动装配

`src/main.cpp` 仅将 argc/argv 交给 `RunServer`。`bootstrap.cpp` 是实际组合根：加载配置和日志，创建 data_dir 和 NamespaceManager，打开独立 platform.db，再打开 catalog.db 并运行 schema migration，构造 namespace/unit router、资源池和 WriteCoordinator 工厂，验证模型、建立 parser/chunker/enricher，初始化 tasks.db，连接 SPC 与异步 WorkerPool，然后注册路由、trace、health、GC 和关闭回调。

SPC 与异步任务相互调用形成装配依赖：DocumentProcessor 使用 SPCManager 的 post-parse 入口，SPC 可 enqueue 文档摘要任务到 WorkerPool，因此 bootstrap 通过后安装 seam / proxy 解决构造时循环，不能把它解释成递归执行。

资源池的 Unit 加载负责打开向量索引、store.db、coordinator 和 memory.db；P-HNSW 从 snapshot/WAL 恢复后才接受服务，coordinator 需要 metadata/blob 探针和补偿回调。不要依据 bootstrap 对“lazy”的历史注释推断每个资源都已在启动时打开，应结合 `NamespacePool` 的公共 load 路径。

## 并发和关闭

HTTP 请求线程、SPC 工作队列、F42 持久任务 worker、跨 NS fan-out executor、HNSW snapshot 后台线程、目录 watcher、GC、清理 cron 是不同执行域。查询 wiring 中的共享 ExecutorEngine 构造参数为 8 workers / 500 queue；这不是所有后台线程的总数。SQLite 以 serialized 模式编译，同一连接内部序列化；多个 Unit 的独立连接仍可并行。

SIGINT/SIGTERM 将 readiness 切换至 draining 并停止 listener；main 返回后停止 watcher、GC、cleanup、metrics，并执行 graceful drain 与资源释放。退出时的补偿、排空和下一次 WAL 恢复是不同层次，不能用 HTTP 正常退出代替恢复验证。

## 构建依赖

`cmake/Dependencies.cmake` 固定拉取 cpp-httplib、yaml-cpp、nlohmann/json、spdlog、SQLite amalgamation、ONNX Runtime，测试另依赖 GoogleTest、RapidCheck 和 Benchmark；hnswlib 为仓库内 P-HNSW fork。SQLite 启用 FTS5、JSON1、THREADSAFE=1。ONNX 可关闭；CPU/CUDA flavor 与 execution provider 配置需区分，Apple 构建可启用 CoreML。缺失真实模型时部分实现允许 stub / heuristic，不能将离线测试成功当作真实推理证据。
