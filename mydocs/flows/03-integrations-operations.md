# 集成、长期记忆和运维 IO

Archify 重绘：[09-agent](../diagrams/archify/09-agent/09-agent.html) · [10-mcp-sdk](../diagrams/archify/10-mcp-sdk/10-mcp-sdk.html) · [11-observability](../diagrams/archify/11-observability/11-observability.html)

[Agent 时序](../diagrams/09-agent.mmd) · [接入图](../diagrams/10-mcp-sdk.mmd) · [观测图](../diagrams/11-observability.mmd)

## Web UI

`main.tsx` 启动 React，`routes.tsx` 管理 public bootstrap/login、PrivateRoute 下的 namespaces/upload/search/agent/memory/settings/health/admin，以及企业功能 placeholder。路由 lazy load 只影响前端资源加载，不意味着对应后端能力可用。

页面和 hooks 调 `web/src/api/*`；通用 `client.ts` 用 fetch、credentials=include，非安全方法附 CSRF cookie echo header，记录 API latency；204/空响应返回 undefined，其他成功读 JSON，失败构造 ApiError。上传 helper 使用 XMLHttpRequest/FormData/progress，是独立实现，不能默认继承 request() 的全部 header/cookie 行为；聊天 SSE 也应单独追 Chat 组件流式调用。

UI 使用 React Query 做服务器状态管理，并有 Zustand 状态、i18next 和 telemetry。页面展示、数据缓存、HTTP 持久化是三层不同状态。

## SDK 和 MCP

SDK 同步/异步 clients 将 resource 方法映射到 HTTP；资源包括 namespaces、documents、query、memory、imports、auth、ops、watchers、tenants、system、sql、sync。resource 的存在不是服务端对应功能已支持的证据。base clients 负责 timeout/retry/error 映射；类型有 generated 与手写模型，维护需核对 OpenAPI。

MCP 本地 stdio server 注册 core/new/extended/memory/admin 工具，直接调 `transport.request` 到 `{CORTRIX_URL}/api/v1`。transport 维护共享 httpx Client，注入 Bearer 和 X-Session-Id/X-Trace-Id/X-Agent-Id，timeout/connection error 转 transient，业务错误尽量透传。session_id 是进程级关联 ID，不是远程 MCP protocol session；每请求生成独立 trace_id。success envelope 保留 coverage_ratio、namespaces_failed 和分页字段。远程 Streamable HTTP 是路线图，不是当前架构图的网络入口。

Skills 的 descriptor/toolkit 定义工具能力与执行，adapters 转换为 OpenAI、Claude、LangChain 格式；它不承担独立数据库持久化，也不是 FastAPI Agent 的 autonomous executor。

## 固定 RAG Agent

FastAPI route 获取 ChatContext 与 SessionStore 历史，然后 ChatExecutor 通过 SDK 召回，最多 3 次尝试，间隔 500/1000ms；耗尽后用空上下文调用 LLM，并设置 rag_status=degraded。源码 `_retrieve_with_retry` 捕获 Exception，不能只依据模块注释声称实现已严格按 transient 分类重试。

Executor 组织带 source_path 的 chunk 文本，额外 best-effort 列文档清单，再通过 prompt builder 注入上下文和历史，调用 llm adapter stream_chat。输出 StreamEvent chunk/meta，chat route 编成 SSE data frames 和 `[DONE]`。C++ agent proxy 负责转发而不是执行 Python LLM。

LLM adapters 包含 OpenAI、Claude、DeepSeek、GLM、Ollama 和 mock；实际选择由 Agent 配置决定。SessionStore 是带锁进程内 dict，最近 10 turns 滑动窗口，服务重启不持久化。ToolUseExecutor 是 NotImplementedError 预留，不应宣称支持自主 tool planning。

## Memory IO

显式 memory 写入经 MemoryWriter/Store 和相关 block adapter，查询由 searcher/scorer 提供；注入、透明度、opt-out、矛盾检测和 extraction queue 有实现。自动 LLM memory extraction、RBAC、tenant isolation 的公开状态仍是开发中。手动 memory API 与自动抽取能力应分别评估。当前 compatibility 还明确指出：显式 memory 可写、列、改、删，但本版本 `/memory/search` 和 `/query` 不返回这些显式 memory 的语义搜索结果；MemorySearcher 类存在不能用来推翻此支持边界。

interaction_log 与 interaction_sources 存在每 Unit/NS 的 memory.db，而 agent_trace 已迁移到全局 catalog.db，允许同 session 跨 NS。trace 查询不能简单要求一个 namespace 参数后只读单库；interactions 需根据来源/namespace/user 关系解析并遵守权限。

## 健康、日志和后台清理

Readiness 注册 disk、catalog、secret provider、SPC workers、模型等组件探针，Quick Start 增加 demo ready marker。live 与 ready 含义不同；ready 成功并不单独证明所有延迟加载 namespace 索引和 memory 功能都健康。

ObservabilityContext 接受经过校验的关联 headers；HTTP middleware 和 EngineInstrumentation 记录请求及阶段 trace，OperationLogger 记录业务操作。trace/operation log 是数据库记录，spdlog 是运行日志，metrics 是计数/分布，三者不是同一输出。Web telemetry 另有浏览器侧延迟与页面数据。

cleanup scheduler、interaction log sweeper、task cron、enrichment retry/backfill、GC 和 snapshot 都有各自生命周期。Directory watchers 的当前契约说明移除 watcher 会清除它导入的文档，`GET /watch/{id}/events` 本版本未实现并返回 404。删除请求、逻辑 tombstone、引用消失、后台 blob 删除不是同时完成。批量临时输入清理与持久 blob GC 也应分开检查。

## 当前能力边界

README/compatibility 将 local core、health、namespaces/documents/query、MCP、SDK、fixed-flow Agent 列为 Preview；auth login、tenant/member/ACL/quota、自动 memory extraction、RBAC/tenant isolation、database import 列为 In development。以上是本地仓库声明，未在线核验。分析图反映代码关系，不提升这些能力的支持等级。
