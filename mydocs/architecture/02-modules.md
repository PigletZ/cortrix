# 模块职责、输入输出与代码导航

Archify 重绘：[01-system](../diagrams/archify/01-system/01-system.html) · [10-mcp-sdk](../diagrams/archify/10-mcp-sdk/10-mcp-sdk.html)

下表覆盖 `src/` 的一级模块（vendor 不单独解释）。每个模块完整文件列表见 [源码索引](../reference/source-inventory.md)。接口头文件通常位于同名 `include/cortrix/` 目录；个别历史接口如 `reranker.h`、`spc_enricher.h`、`memory_scorer.h` 位于 include 根。

| 模块 | 职责 / IO / 边界 |
|---|---|
| `src/common/` | Result/Status、Block 类型、全局配置和 ExecutorEngine；被业务层共享；避免把通用 error 与 HTTP status 混为一谈。 |
| `src/config/` | YAML/env/CLI 配置及 FileBasedGlobalConfig；向 bootstrap 和运行时 resolver 输出有效配置。 |
| `src/server/` | HTTPServer、bootstrap、route registration、batch/import service；处理协议和装配，不承担全部检索算法。 |
| `src/auth/` | platform.db、API key、JWT、密码散列、bootstrap/admin services；代码存在，公开支持状态仍受 compatibility 限制。 |
| `src/catalog/` | 全局 namespace/unit/content-reference 路由、schema migration、GC；输入逻辑实体，输出 Unit 位置与引用状态。 |
| `src/namespace/` | NamespaceManager 管理 namespace 生命周期和目录；与 catalog 路由、资源池配合。 |
| `src/resource/` | NamespacePool、NamespaceFacade、NamespaceResourceBundle/UnitResourceBundle、SQLite connection；维护资源所有权、加载与回收，向 SPC/query 暴露借用句柄。 |
| `src/upload/` | UploadHandler 校验上传、构造 document/SPCTask、保存输入并提交 SPC；返回接受状态而非保证索引完成。 |
| `src/connector/` | DirectoryImporter、FileWatcher、DirWatcherRegistry、filter/utils；文件变化 → 文档导入/更新/删除，包含 watcher 状态持久化。 |
| `src/async/` | TaskManager(tasks.db)、TaskScheduler、WorkerPool、DocumentProcessor、TaskFinalizer、cleanup；输入持久任务，输出进度与终态。 |
| `src/spc/` | ParserFactory/Docling/PaddleOCR/subprocess、SPCPipeline/SPCManager、embedder、enricher chain、retry/backfill；文件 → ParsedDoc → children → CortrixBlocks。 |
| `src/chunker/` | ParentChildChunker、dedup、config/startup validator；ParsedDoc → parents/children，支持 flat fallback。 |
| `src/metadata/` | RuleBasedMetadataGenerator 与 schema；文档级输入 → META block 文本/字段。 |
| `src/scoring/` | SemanticScorer、score map/store；block/enrichment signals → semantic_score 等质量字段。 |
| `src/store/` | CortrixStoreSqlite、blob local、P-HNSW、PWL、group commit、parent/chunk store；块/向量/文件持久化及恢复。 |
| `src/query/` | CrossNsQueryWiring、classifier、scatter、live executor、vector/BM25/RRF、filters、RAG-Fusion/listwise/CRAG；QueryContext → results + metadata。 |
| `src/retrieval/` | sparse codec/store/index registry、sparse RRF/fallback、CRAG evaluator；稀疏和纠错检索辅助，不是独立 HTTP 服务。 |
| `src/reranker/` | ONNX cross-encoder、tokenization/preprocessing、score fusion、circuit breaker/thread pool/config；query/passages → scores 或降级状态。 |
| `src/doc_summary/` | 摘要 generator、F41AsyncWorker、doc FTS5/discover handler；文档 → summary 索引；doc 路径不等于普通 child 召回。 |
| `src/memory/` | MemoryStore/writer/searcher/injector、extraction/contradiction/queue、transparency/opt-out；结构化长期记录及交互来源，自动 extraction 尚属开发中。 |
| `src/llm/` | ILlmClient、OpenAiLlmClient、HttpTransport；C++ enrichment/summary/query 可选外部 LLM 通道。 |
| `src/ml/` | OrtEnvSingleton、execution provider、TokenizerRegistry；模型运行时共享基础设施。 |
| `src/agent_trace/` | HTTP middleware、EngineInstrumentation、AgentTraceWriter、traces/interactions handlers、sweeper；链路事件 → 全局 trace 与每 NS 交互来源。 |
| `src/observability/` | OperationLogger/Emitter、ObservabilityContext、cleanup scheduler；业务操作日志与关联上下文。 |
| `src/health/` | ReadinessRegistry；组合组件探针结果，输出 live/ready 状态。 |
| `src/deploy/` | DiskMonitor、MetricsServer、GracefulShutdown；磁盘、指标、排空、恢复启动支持。 |
| `src/middleware/` | RateLimiter、AdminGuard；请求流量与管理权限边界。 |
| `src/security/` | EnvSecretProvider / readiness adapter；secret 获取与健康状态，不等于完整密钥管理平台。 |
| `src/import/` | connection/query executor/text serializer/SPC feeder/import manager；数据库记录 → 文本 → SPC seam；部分状态 store 为 in-memory，公开状态开发中。 |
| `src/tenant/` | TenantService、PermissionService、QuotaService / plan provider；多租户和 ACL 代码，不构成已验证隔离承诺。 |
| `src/agent_friendly/` | 统一 Agent 友好错误契约与分类，供 HTTP/MCP/SDK 透传与重试判断。 |
| `src/id/` | ULID、hash、ID types；doc/child/block 的身份和稳定映射。 |
| `src/logging/` | spdlog wrapper、sanitizer、敏感字段配置；运行日志和脱敏支持。 |

## 依赖规则和阅读要点

协议入口依赖业务服务，业务服务通过 facade / store / index / LLM 等接口获得资源。bootstrap 负责具体实现装配，因此不能仅从 include 关系推断运行时调用；同样，CMake 将实现编译进 core 也不等于路由实际触发该实现。`query_pipeline.cpp`、`single_unit_executor.cpp` 与 `live_single_unit_executor.cpp` 同时存在，当前跨 NS HTTP 热路径应优先追 `query_wiring.cpp` → `scatter_gather.cpp` → `live_single_unit_executor.cpp`。

`NamespaceResourceBundle` 聚合多个 UnitBundle，但 namespace 到 Unit 的拓扑和当前 executor 实际遍历方式需分别看 router、facade 与 live executor，不能因此声称系统已支持分布式多节点分片。当前图中的 scatter 是进程内跨 namespace fan-out。

Python MCP 直接 HTTP，Agent 经 SDK，Skills 经 toolkit/adapter 调 SDK；Web 的 feature placeholder 路由只说明 UI 页面存在。维护新功能时需要核对 OpenAPI、C++ route、SDK resource、MCP tool 和 Web API wrapper 五层是否同步。
