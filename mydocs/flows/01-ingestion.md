# 文档入库：输入、处理和输出

Archify 重绘：[03-ingest](../diagrams/archify/03-ingest/03-ingest.html) · [08-async](../diagrams/archify/08-async/08-async.html)

[入库图](../diagrams/archify/03-ingest/03-ingest.html) · [异步图](../diagrams/archify/08-async/08-async.html)

## 入口不是单一路径

| 入口 | 输入 | 中间产品 | 响应后继续发生的操作 |
|---|---|---|---|
| upload/document routes | multipart 文件、namespace、filename、metadata | document + blob / SPCTask | SPC 队列解析和索引；接受不等于完成 |
| directory import/watch | 本地目录、filter、文件事件 | source path、hash、SPCTask | 去重/更新/删除及后台处理 |
| batch routes | 多文档文本/文件与批次元数据 | managed temp input + TaskManager entries | scheduler/WorkerPool 处理并落终态 |
| async document | 大文件及任务参数 | tasks.db 持久任务 | 页级解析进度、post-parse SPC |
| memory SPC 特殊路径 | 显式 memory 文本 | memory block | 直接 embed/assemble/write，绕过普通文档 parse/chunk |
| database import | connection/query/row 文本 | serializer → SPC feeder | 代码与 seam 存在；公开状态开发中 |

## 常规路径逐阶段 IO

1. `UploadHandler` 从上传输入生成/查询 doc 身份和 content_hash，处理更新时取消旧任务等生命周期操作，再构造 source_type、MIME、processing_level、priority 和 metadata_json，调用 `SPCManager::Submit`。文档记录和 task ID 是不同实体。
2. `SPCPipeline::Process` 按 level 处理：L0 跳过，L1 写 metadata-only block；L2/L3 进入 ParserFactory。memory 专用分支单独处理，不能套入普通文档的每一阶段。
3. ParserFactory 将路径和 ParseOptions 交给 primary parser，Docling/PaddleOCR/subprocess 实现负责结构解析、OCR/fallback，输出 ParsedDoc、页信息和 parse error。具体 parser 选择及可用性由配置决定，不是每份文档都顺序执行两套 OCR。
4. `ProcessParsed` 将 ParsedDoc 交给 ParentChildChunker，产出 parents、children、位置关系；空输出或 fallback 有单独分支。
5. 生成文档级 META block，再对 child context 执行 enrichment chain；F03 可提取实体/摘要，F35 产生 contextualized 内容/向量，F38 产生 HyPE 问题 side channel。未配置 LLM 或链为空时走空增强/单 enricher 回退。
6. L3 批量 embed children，可在 sparse registry 已装配时输出 dense+sparse；L2 跳过常规 embedding。META block 与 HyPE 问题可能单独 embedding；这使“向量数=原文 child 数”不成立。
7. block-level DataCleaner 和 skip-index 判定在后续组装区执行，SemanticScorer 使用清洗/enrichment signals，BlockAssembler 将文本、header、embedding、child/parent/doc 身份组合成待写集合。当前源码主路径不是简单的“先清洗全文再解析”。
8. 普通上传先在 UploadHandler 保存 blob，再提交 SPC；ProcessParsed 的 BeginWrite 使用 `writes_blob=false`，先写 doc FTS5 产品，再写 ANN points、parents、blocks 及辅助 enrichment/contextual/sparse/score 状态。主失败补偿 rollback，辅助失败可能仅记录 warning/NULL/retry 状态；Commit 成功后 SPCTask done。
9. F41 摘要生成可通过异步 seam enqueue，依赖 worker/LLM 装配；完成主入库不能直接推断 doc summary 已生成。

## F42 持久任务路径

TaskManager 将状态保存在 tasks.db；Scheduler 选择任务，WorkerPool 执行 DocumentTaskHandler/DocumentProcessor。DocumentProcessor 调 ParserFactory 并通过页回调更新 processed_pages、total_pages、failed_pages、progress_pct；ETA 在所读代码中仍可为 -1，不能误写成可靠剩余时间预测。

解析完成后调用 `SPCManager::ProcessParsedDoc`，复用分块到写入的全部后半段。该路径实际装配时使用 L3；没有 spc_mgr 的 standalone/test 场景可 parse-only finalize，不能拿这个分支描述生产完整入库。

取消在页检查点和解析后检查，不代表立即强杀 subprocess。传给 post-parse 的 SPCTask 没有完整中途取消传播，源码注明后处理阶段更细的 cancel 属后续工作。TaskFinalizer 负责 complete/fail/cancel 持久终态；TaskCleanupCron 清理历史任务。

## 结果检查与排障

响应成功但搜索为空，依次核对 document/任务是否仅 accepted、task 终态、processing_level、解析输出、清洗 skip-index、namespace 与 Unit 映射、模型是否真实加载、ANN 和 FTS5 是否写入、query filter 是否丢弃。避免通过客户端多次重复上传来推断任务已完成；相同来源更新和不同 doc_id 的语义可能不同。

失败信息应保留 task_id/doc_id、parser error、failed_pages、SPC stage、structured_data 与 trace_id。`pending.wal` 只参与持久写阶段，解析阶段失败不会自动意味着需要执行三存储恢复。
