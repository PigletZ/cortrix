# 架构与 IO 图集（Mermaid 原版）

**新版入口：[Archify 交互图集](archify/index.html)**。原版保留作对照；blob/PWL 和双层 GC 的精确边界以重绘版及更新文档为准。

图源基于当前源码；可选能力不代表默认开启，流程细节以配套文档为准。

## 01 系统与进程边界

[独立图源](01-system.mmd)

```mermaid
flowchart TB
  User[用户 / 应用 / IDE Agent]
  User --> Web[web: React + TypeScript + Vite]
  User --> SDK[sdk/python: Sync / Async Client]
  User --> MCP[cortrix-mcp: local stdio]
  User --> Skills[cortrix-skills: tool descriptors / adapters]
  Skills --> SDK
  MCP -->|httpx HTTP JSON + identity headers| HTTP
  SDK -->|HTTP JSON| HTTP
  Web -->|fetch JSON / multipart / SSE| HTTP
  HTTP[cortrix-server: cpp-httplib / api/v1] --> Routes[鉴权 / 限流 / 路由 / trace]
  Routes --> Catalog[catalog: NS / Unit / content refs]
  Routes --> Ingest[upload / connector / batch / async]
  Ingest --> SPC[SPC: parse / chunk / enrich / embed / assemble]
  Routes --> Query[query: router / scatter / hybrid / rerank]
  Routes --> Memory[memory: store / search / transparency]
  SPC --> Pool[resource: NamespacePool / Facade / UnitBundle]
  Query --> Pool
  Memory --> Pool
  Pool --> Store[SQLite store.db / memory.db]
  Pool --> ANN[P-HNSW / hnsw.wal / snapshots]
  Pool --> Blob[Unit blob files]
  Pool --> PWL[WriteCoordinator / pending.wal]
  Routes --> AgentProxy[agent_proxy_routes]
  AgentProxy -->|HTTP / SSE| Agent[cortrix-agent: FastAPI / ChatExecutor]
  Agent --> SDK
  Agent -->|stream_chat| LLM[外部 LLM / Ollama]
  SPC -. 可选 enrichment / summary .-> LLM
  Query -. 可选 query expansion / listwise .-> LLM
  SPC --> ONNX[ONNX Runtime / tokenizer / local models]
  Query --> ONNX
  Catalog --> Global[catalog.db / platform.db / tasks.db]
```

## 02 启动与关闭

[独立图源](02-bootstrap.mmd)

```mermaid
flowchart TD
  Main[src/main.cpp] --> Run[RunServer: bootstrap.cpp]
  Run --> Config[CLI / YAML / env 配置与日志]
  Config --> NS[NamespaceManager / data_dir]
  NS --> Auth[platform.db / API keys / JWT services]
  Auth --> Cat[catalog.db / schema providers / migration]
  Cat --> Pool[NS router / Unit router / NamespacePool]
  Pool --> Models[ONNX 验证 / embedder / tokenizer]
  Models --> Parse[ParserFactory: primary / fallback]
  Parse --> Chain[chunker / metadata / enrichment chain]
  Chain --> Tasks[tasks.db / TaskManager / Scheduler]
  Tasks --> SPC[SPCPipeline → SPCManager]
  SPC --> Workers[DocumentProcessor / WorkerPool / summary workers]
  Workers --> HTTP[HTTP routes / query wiring / observability]
  HTTP --> Ready[readiness probes / metrics / shutdown hooks]
  Ready --> Start[SPC + async workers + GC + cleanup + watchers]
  Start --> Listen[HTTP server.Start]
  Listen --> Signal[SIGTERM / SIGINT → draining]
  Signal --> Stop[停止 watcher / GC / cron / metrics / 排空任务 / RAII 释放]
```

## 03 文档入库流水线

[独立图源](03-ingest.mmd)

```mermaid
flowchart TD
  File[文件字节 / 路径 / MIME / metadata] --> Upload[UploadHandler / directory importer / batch]
  Upload --> Identity[doc_id / content_hash / document record]
  Identity --> Route{处理入口}
  Route -->|常规| Q[SPCTaskQueue → SPC worker]
  Route -->|持久化异步任务| T[tasks.db → Scheduler → WorkerPool]
  T --> Parser[DocumentProcessor / ParserFactory]
  Q --> Level{processing_level}
  Level -->|L0| Skip[跳过 SPC 处理]
  Level -->|L1| MetaOnly[metadata-only block]
  Level -->|L2 / L3| Parser
  Parser -->|ParsedDoc| Chunk[ParentChildChunker / flat fallback]
  Chunk --> Meta[规则元数据生成 F08]
  Meta --> Enrich[可选 F03 entities-summary / F35 contextual / F38 HyPE]
  Enrich --> Embed{L3?}
  Embed -->|是| Vec[OnnxEmbedder: dense + 可选 sparse]
  Embed -->|L2 跳过 embedding| Clean
  Vec --> Clean[DataCleaner: block-level 清洗 / skip-index]
  Clean --> Score[SemanticScorer / BlockAssembler]
  Score --> Begin[WriteCoordinator.BeginWrite → pending.wal]
  MetaOnly --> Begin
  Begin --> Persist[blob / ANN / parents / blocks / FTS5 / auxiliary rows]
  Persist --> Commit[WriteCoordinator.Commit]
  Persist -->|核心写失败| Rollback[Rollback / 补偿清理]
  Commit --> Done[任务 done / document 可检索]
  Done -. 配置启用 .-> Summary[F41 摘要异步任务 / doc index]
```

## 04 查询召回与融合

[独立图源](04-query.mmd)

```mermaid
flowchart TD
  Req[POST api/v1/query: query / namespaces / top_k / filter] --> Validate[parse / auth / authorize namespaces]
  Validate --> Router[F39 complexity classifier: ONNX 或 heuristic]
  Router -->|chat 路由| Facts[按用户查 user_facts / 跳过检索]
  Router -->|simple / complex| Scatter[ScatterGather + ExecutorEngine]
  Scatter --> Acquire[每个 namespace 获取 NamespaceFacade]
  Acquire --> Gran{granularity}
  Gran -->|chunk| Chunk[LiveSingleUnitExecutor chunk path]
  Gran -->|doc| Doc[doc summary ANN / doc FTS5]
  Gran -->|auto / both| Both[chunk + doc → doc_id 级融合]
  Both --> Chunk
  Both --> Doc
  Chunk --> Dense[query embedding → P-HNSW dense]
  Chunk --> BM25[SQLite FTS5 / BM25]
  Chunk -. 启用且可用 .-> Sparse[sparse embedding → sparse index]
  Dense --> Resolve[解引用 child / contextual label / HyPE source]
  BM25 --> Resolve
  Sparse --> Resolve
  Resolve --> RRF[多路径 RRF / 过滤 / 候选过采样]
  RRF --> Rerank[可选 ONNX cross-encoder + score fusion]
  Rerank --> Local[每 NS top_k + metadata]
  Doc --> Local
  Local --> Gather[排序 / content_hash 去重 / global top_k]
  Gather -. 开关与依赖满足 .-> RAG[RAG-Fusion 多 query 变体与二次检索]
  Gather --> Post[可选 CRAG / LLM listwise 阶段]
  RAG --> Post
  Post --> Response[results + coverage_ratio + namespaces_failed + explain]
  Facts --> Response
```

## 05 跨命名空间查询时序

[独立图源](05-query-sequence.mmd)

```mermaid
sequenceDiagram
  participant C as HTTP client
  participant W as CrossNsQueryWiring
  participant S as ScatterGather
  participant P as NamespacePool
  participant E as LiveSingleUnitExecutor
  participant M as ONNX models
  participant D as SQLite / ANN / sparse
  C->>W: POST /api/v1/query
  W->>W: validate + auth + classify + build QueryContext
  W->>S: authorized namespace fan-out
  par Namespace A
    S->>P: Acquire namespace facade
    P-->>E: store + index + memory handles
    E->>M: embed query
    M-->>E: dense / optional sparse vector
    E->>D: dense ANN / BM25 / optional sparse
    D-->>E: candidates + source rows
    E->>E: RRF + filter + source resolution
    E->>M: optional ScoreBatch(query, passages)
    M-->>E: rerank scores
    E-->>S: NamespaceQueryResult
  and Namespace B or others
    S->>E: execute with deadline
    E-->>S: success or structured failure
  end
  S->>S: sort + content-hash dedup + truncate
  S-->>W: results + coverage + failures
  W->>W: enabled optional stages + trace
  W-->>C: JSON response
```

## 06 物理存储与逻辑资源

[独立图源](06-storage.mmd)

```mermaid
flowchart TB
  Root[data_dir] --> Platform[platform.db: auth / secrets / keys]
  Root --> Catalog[catalog.db: namespace / unit / refs / trace / op log]
  Root --> Tasks[tasks.db: persistent async task states]
  Root --> Units[units / unit_id]
  Root --> Sparse[namespace / sparse_index.db]
  Units --> DB[store.db: documents / blocks / parents / FTS5 / aux]
  Units --> Mem[memory.db: memory / interaction log / sources]
  Units --> Blob[blob / doc_id: source bytes]
  Units --> WAL[hnsw.wal: vector operation log]
  Units --> Snap[HNSW snapshots]
  Units --> Pending[pending.wal: cross-store write intent]
  NS[Namespace logical identity] --> Router[DefaultINSRouter / DefaultUnitRouter]
  Router --> Bundle[NamespacePool / UnitResourceBundle]
  Bundle --> Units
  Bundle --> Facade[NamespaceFacade: store / vec_index / memory / coordinator]
```

## 07 跨存储写入与崩溃恢复

[独立图源](07-write-recovery.mmd)

```mermaid
sequenceDiagram
  participant S as SPCPipeline
  participant W as WriteCoordinator
  participant P as pending.wal
  participant B as Blob store
  participant V as PHnsw
  participant D as SQLite store
  S->>W: BeginWrite(doc_id, block_ids, has_blob)
  W->>P: append PENDING / group commit
  W-->>S: TxnHandle
  S->>B: source blob when required
  S->>V: AddPoints
  V->>V: append hnsw.wal → fdatasync → apply graph
  S->>D: parents / blocks / FTS5 / auxiliary rows
  alt primary writes successful
    S->>W: Commit(txn)
    W->>P: append COMMITTED / retry / optional compact
  else primary write failed
    S->>W: Rollback(txn)
    W->>D: compensating cleanup callback
    W->>V: remove failed write points
    W->>P: terminal rollback record
  end
  Note over W,D: No distributed SQL transaction across these stores
  Note over W,P: Restart: read pending records, probe required stores, infer commit or compensate
```

## 08 持久化异步任务

[独立图源](08-async.mmd)

```mermaid
flowchart LR
  Input[batch / document submission] --> Managed[managed input files / task metadata]
  Managed --> TM[TaskManager / tasks.db]
  TM --> Scheduler[TaskScheduler priority queue]
  Scheduler --> Pool[WorkerPool bounded workers]
  Pool --> Handler[DocumentTaskHandler]
  Handler --> Processor[DocumentProcessor]
  Processor --> Parse[ParserFactory / subprocess]
  Parse -->|page progress| TM
  Parse -->|ParsedDoc| SPC[SPCManager.ProcessParsedDoc]
  SPC --> Persist[shared post-parse SPC / durable writes]
  Persist --> Final[TaskFinalizer complete / fail / cancel]
  Final --> TM
  Client[client poll / cancel] --> TM
  Cron[TaskCleanupCron / cleanup registrar] --> TM
```

## 09 固定 RAG Agent 时序

[独立图源](09-agent.mmd)

```mermaid
sequenceDiagram
  participant U as Web / client
  participant C as C++ agent proxy
  participant A as FastAPI chat route
  participant E as ChatExecutor
  participant S as Python SDK / Cortrix query
  participant L as configured LLM adapter
  U->>C: chat request
  C->>A: forward HTTP
  A->>A: session history / context
  A->>E: execute(message, context)
  E->>S: retrieve relevant chunks
  S-->>E: chunks / sources / meta
  Note over E,S: retrieval retry up to 3 attempts; exhaustion degrades to no-context prompt
  E->>S: best-effort document inventory
  E->>E: build prompt + sources + recent history
  E->>L: stream_chat
  L-->>E: text pieces
  E-->>A: StreamEvent chunk / terminal meta
  A-->>C: SSE data frames + DONE
  C-->>U: streamed response
  Note over A: SessionStore is in-process memory, not durable storage
```

## 10 MCP、SDK 与 Skills

[独立图源](10-mcp-sdk.mmd)

```mermaid
flowchart TD
  IDE[IDE Agent] -->|MCP local stdio| MCP[mcp_server / server registration]
  MCP --> Tools[tools core / new / extended / memory / admin]
  Tools --> Transport[transport.request / httpx]
  Transport --> Headers[Bearer + X-Session-Id + X-Trace-Id + X-Agent-Id]
  Headers --> Core[C++ HTTP API]
  Core --> Envelope[MCP envelope / errors / coverage fields]
  Envelope --> IDE
  App[Python app / ChatExecutor] --> Client[Cortrix / AsyncCortrix]
  Client --> Resources[documents / query / namespaces / memory / ops / etc]
  Resources --> Base[base HTTP client / retry / timeout / error mapping]
  Base --> Core
  Framework[OpenAI / Claude / LangChain integrations] --> Toolkit[cortrix-skills toolkit + descriptor]
  Toolkit --> Client
```

## 11 可观测性与健康检查

[独立图源](11-observability.mmd)

```mermaid
flowchart TD
  HTTP[HTTP request / caller identity headers] --> Middleware[ObservabilityContext / HTTP trace middleware]
  Middleware --> Engine[EngineInstrumentation: retrieval stages]
  Middleware --> Ops[OperationLogEmitter / OperationLogger]
  Engine --> Trace[AgentTraceWriter → catalog.db]
  Ops --> Catalog[operation log → catalog.db]
  Chat[chat / interaction APIs] --> Interaction[memory.db interaction_log / interaction_sources]
  Trace --> TraceRead[traces / interactions routes]
  Interaction --> TraceRead
  Cleanup[cleanup scheduler / InteractionLogSweeper] --> Trace
  Cleanup --> Interaction
  Health[readiness registry] --> Probes[disk / catalog / secret provider / SPC / models / quickstart marker]
  Probes --> Ready[live / ready HTTP]
  Counters[module metrics + latency] --> Metrics[metrics server]
```

## 12 删除与 GC

[独立图源](12-delete-gc.mmd)

```mermaid
flowchart TD
  Req[document / namespace delete] --> API[routes / namespace manager / catalog]
  API --> Logical[logical delete / content-reference update]
  Logical --> Queue[catalog GC state / blob_gc_queue]
  Queue --> GC[GcThread → GcManager / DocumentGcSweeper]
  GC --> Ref{remaining references?}
  Ref -->|yes| Keep[retain shared resources]
  Ref -->|no| Clean[block / vector / parent / document cleanup]
  Clean --> Sink[LocalBlobGcSink]
  Sink --> FS[delete eligible blob files]
  GC --> Audit[metrics / log / retry state]
```
