# 检索 IO：路由、召回、排序与完整性

Archify 重绘：[04-query](../diagrams/archify/04-query/04-query.html) · [05-query-sequence](../diagrams/archify/05-query-sequence/05-query-sequence.html)

[查询流程](../diagrams/archify/04-query/04-query.html) · [跨 NS 时序](../diagrams/archify/05-query-sequence/05-query-sequence.html)

## 当前主入口

优先阅读 `src/query/query_wiring.cpp`，其中 CrossNsQueryWiring 注册并装配 HTTP 热路径、TenantPermissionAdapter、ExecutorEngine、LiveSingleUnitExecutor、ScatterGather、classifier 及可选增强阶段。仓库其他 QueryPipeline 实现仍有价值，但不能把全部历史类串成同一次 HTTP 请求。

输入是 query、namespaces、top_k、rerank、search_config、filter、granularity 等 JSON/参数。MakeRoutingContext 会拷贝 query/top_k/rerank/filter/identity 和各召回开关；合法值与错误以 route/parse contract 为准，内部 clamp 不能替代对外参数校验。输出 results 与 meta，不是自然语言最终回答。

## 路由和 fan-out

授权先处理 namespace universe；auth-disabled CE 路径直接允许读取，wildcard 枚举 pool 的 active namespaces，因此不能根据该实现声称 wildcard 扫描了所有磁盘 namespace。开启 auth 时通过 TenantPermissionAdapter 重建 AuthContext，再调用 tenant permission service。

ComplexityClassifier 优先可用 ONNX backend，否则 heuristic；错误/低置信度有保守回退。chat routing path 仅查询按用户的 user_facts，跳过所有 retrieval；它与 FastAPI ChatExecutor 的 RAG 聊天是不同功能。

ScatterGather 使用共享线程池分发 namespace 工作，并设置 deadline/timeout。每个 namespace 返回 NamespaceQueryResult 或结构化失败。fan-out 不代表跨机器 RPC。

## 单 namespace 的候选来源

| 路径 | 输入 / IO | 输出与注意点 |
|---|---|---|
| dense | query → OnnxEmbedder → ANN search | point labels / distances；需恢复 child/source 身份 |
| lexical | query → SQLite FTS5 / BM25 | block/child 候选；支持无 dense 的词项路径 |
| sparse | query sparse embedding → namespace sparse index | 可选；registry 必须与 ingest 共用，缺失时降级 |
| contextual | enriched 向量 ANN label → contextual mapping | 还原原文 child，缺失 mapping 可丢该 ANN hit |
| HyPE | 问题 block vector hit → source child | 问题文本用于召回，原始来源用于结果证据 |
| doc discovery | doc summary ANN / doc FTS5 | doc 级 metadata / one-liner；排序语义区别于 child |

LiveSingleUnitExecutor 根据 granularity 选择 chunk/doc/auto/both；auto/both 路径合并文档与 child 结果时按 doc_id 融合，因此不应总按 child_id 理解最终去重。doc path 中 match_score 可直接作为 rerank_score 的兼容值，不表示真正执行过 cross-encoder。

chunk path 过采样候选，合并 dense、BM25、sparse/contextual/HyPE 路径，用 FuseFivePathRrf 得到融合分数，再解析源块与 metadata、执行过滤和可选 rerank。具体过滤位置存在多处，不能将 flowchart 一条箭头理解成全部过滤只执行一次。

## 重排和跨 NS 汇总

当 rerank 开启，单 NS chunk path 调 ScoreBatch(query, passages)，使用 RerankerScoreFusion 组合 cross-encoder 与 RRF，源码默认解释为 0.7/0.3，并有附加 signal/config 语义；它不是所有路径固定通用权重。模型目录为空可为 stub；这与“真实 BGE cross-encoder 已执行”需要分开。

ScatterGather 的 `GatherAndRerank` 名称容易误导：当前实现主要收集各 NS 已排序结果、按 final score 排序、按 content_hash 去重，再截断 global top_k；不能仅从函数名推断又执行了一次全局神经重排。content hash 根据实际 chunk_text 计算，与 block header 的截断 SHA-256 约定一致，保留最高分 primary 并记录多来源。

RAG-Fusion 会在开关/LLM 依赖满足时生成 query variants、二次检索和融合；CRAG 有 heuristic guard 及 fail-soft，LLM listwise 同样有开关与依赖门控。这些是 query_wiring 的可选分支，图中的后处理框是概括，实际顺序和启用条件应沿该文件对应 route lambda 阅读，不能默认每次都走。

## 完整性、失败和消费契约

`coverage_ratio = namespaces_succeeded / namespaces_queried`（空集合内部默认 1）。某些 NS 超时或失败时成功 NS 的结果可返回，同时 namespaces_failed 记录 code/category/retryable/retry_after_ms/structured_data。coverage 表示 NS 执行覆盖率，不是答案正确率、召回率或文档扫描比例。

rerank=false 会生成 `CX_WARN_RERANK_DISABLED`，消费者应理解排序来自融合。全失败、参数错误、权限失败与部分成功不是同一响应状态；以 handler 和 OpenAPI 的对应分支核对 HTTP code。MCP/SDK/Agent 必须保留完整性 meta，不能只读取 results 就声称检索覆盖全部目标 NS。

外部 LLM 未配置、classifier 模型缺失、sparse 不可用、辅助 label 缺失都可能走降级，而核心 embedding/ANN 失败的影响不同。调试应查看 explain、warnings、route/path 和 trace，不能把“有结果”当作全部检索通道都已执行。
