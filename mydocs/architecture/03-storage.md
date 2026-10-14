# 数据模型、物理 IO 与一致性

Archify 重绘：[06-storage](../diagrams/archify/06-storage/06-storage.html) · [07-write-recovery](../diagrams/archify/07-write-recovery/07-write-recovery.html) · [12-delete-gc](../diagrams/archify/12-delete-gc/12-delete-gc.html)

[存储图](../diagrams/archify/06-storage/06-storage.html) · [写入恢复时序](../diagrams/archify/07-write-recovery/07-write-recovery.html)

## 逻辑实体

| 实体 | 关联 / 用途 | 关键读写方 |
|---|---|---|
| Namespace | 集合边界、配置、授权入口，映射一个或多个 Unit | namespace/catalog/router/pool |
| Unit | 实际持久资源组合，包含 SQLite、ANN、WAL、blob | resource/pool/facade |
| Document | 来源、文件名、MIME、content_hash、metadata、处理状态 | upload/connector/SPC/document routes |
| Parent | 大上下文文本与父标识 | ParentChildChunker/store/parent-child result handling |
| Child / Block | 搜索文本、header、doc/parent 关联、hash、score signals | SPC/store/live executor |
| META block | 文档级元数据产品；可有独立 embedding | metadata/SPC/doc-discovery |
| HyPE question | 派生假设问题 block；召回需映射原始来源 child | enrichment/SPC/live executor |
| Contextual vector | 原始 child 以外的上下文化向量及 label 映射 | F35 store / query source resolution |
| Memory / interaction | 长期记录、user facts、交互与来源引用 | memory/routes/agent_trace |
| Task | 独立持久化异步任务身份、页进度、状态与错误 | async manager/processor/finalizer |

`block_id` 和 `child_id` 不可混用：live executor 优先 `HashChildIdToBlockId(child_id)` 读取源块并检查 child_id，旧数据可通过 SqliteChunkStore 反向索引回退。HyPE/contextual 的索引标签也不能直接当作来源文档 ID。

## 实际落盘

以 `config.ns.data_dir` 为根；下表来自 bootstrap 与 NamespacePool，文件布局不能只依据旧注释中的 `<data_dir>/<namespace>/store.db`。

| 路径 | IO 内容 | 所有者 |
|---|---|---|
| `platform.db` | auth schemas、API keys、JWT secret / users | auth PlatformDb |
| `catalog.db` | namespace/unit/ref 元数据、agent_trace、operation log、GC 状态 | CatalogDb 与借用连接服务 |
| `tasks.db` | F42 任务状态、进度、终态 | TaskManager |
| `units/<unit_id>/store.db` | documents、blocks、parents、FTS5、enrichment、scores、sparse vectors、contextual labels 等 | pool SQLite connection / store adapters |
| `units/<unit_id>/memory.db` | memory、interaction_log、interaction_sources 等 | MemoryStore / namespace facade |
| `units/<unit_id>/blob/<doc_id>` | Unit 层原始输入内容 | local blob backend |
| `units/<unit_id>/pending.wal` | PENDING / COMMITTED / ROLLBACK 事务意图 | WriteCoordinator |
| `units/<unit_id>/hnsw.wal`、snapshot 文件 | 向量增删日志与图快照 | PHnsw / SnapshotManager |
| `<namespace>/sparse_index.db` | namespace sparse registry 索引文件 | SparseIndexRegistry |
| batch temporary / managed input | 上传或批量异步解析输入暂存；具体路径由 helper 计算 | BatchTempStore / ManagedInput |

bootstrap 另外构造全局 `<data_dir>/blobs` GC sink，供 GcManager 的内容引用层清理；DocumentGcSweeper 单独通过 namespace facade 依次执行向量 MarkDelete、Unit blob.del、block/doc delete。两者由 GcThread 驱动，是不同路径。SQLite 自身在 WAL 模式下还可能生成 `-wal` / `-shm` sidecar；它们与 `pending.wal` 和 `hnsw.wal` 的语义不同。

## 三种 WAL

1. SQLite WAL 只负责本 SQLite 数据库事务和页恢复。
2. HNSW WAL 负责向量操作。PHnsw 的 ApplySink 在 group commit 中先 WriteBatch、Sync/fdatasync，再更新内存图；snapshot 后台线程按阈值生成快照。打开时加载最新可用 snapshot 并 replay WAL。
3. pending.wal 是跨 blob、ANN、metadata 的操作意图日志。BeginWrite 记录待写 doc/block 集合和 blob 要求，再执行各存储写入；Commit 写终态，Rollback 调补偿回调并写终态。

SPC 明确注明 F25 是纯 PWL，写块时不持有跨存储 SQLite transaction，因此整体是补偿恢复协议，不能画成一个 ACID 数据库事务。普通上传 blob 由 UploadHandler 在提交 SPC 前保存，ProcessParsed 调 BeginWrite 时设 writes_blob=false；一般接口支持 blob 探针，不代表该路径把上传 blob 纳入同一次 PWL。

BeginWrite 阻止同 doc 并发写，GroupCommitWriter 可以合并不同请求的日志同步。

## 恢复判定和异常语义

Recover 扫描 pending records、按 txn 聚合。已 committed 的不撤销；无终态的 pending 使用 AllStoresHave 检查所要求 blob、block IDs 和 vector points 是否齐全：齐全可推断 committed，缺项执行补偿。之后补终态、compact 并重新初始化事务编号。这个检查依据主存储，不意味着每个可选 enrichment/sparse 辅助产品都已存在。

Commit 终态日志失败会重试；若主存储已经完成但重试耗尽，会返回错误，同时数据仍可能已持久化，恢复可推断提交。调用方不得将“返回失败”简单等价为“完全未写入”。核心写失败触发 rollback；F03/F07/F35 等辅助字段失败有 fail-soft 路径，可能保留主块但缺少增强字段，应通过状态和日志判断。

## 生命周期和 GC

Pool 持有 UnitBundle，facade 借用资源。加载顺序确保 store 与 recovery adapter 先于 coordinator Recover 可用；释放顺序必须避免 rollback callback 指向已释放连接。memory.db 在 Unit load 中预热 schema/WAL，不能假定首次 memory 请求才建库。

删除涉及逻辑状态、引用计数、向量/块清理和 blob 延迟回收。[GC 图](../diagrams/archify/12-delete-gc/12-delete-gc.html) 是模块级概括，各删除 API 是否同步清理以及 GC sink 是否覆盖其物理目录仍需按对应实现和集成测试确认。
