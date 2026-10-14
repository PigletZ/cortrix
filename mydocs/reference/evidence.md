# 分析证据与验证范围

基线 commit：`351f48958cc48bef47f35cf81d6809bc6a5be7a2`。本次是源码阅读与文档整理，没有执行 Core 构建、运行服务、模型推理、集成测试或 benchmark。未访问远程 README 引用页面；对本地代码的分析不依赖网络资料。

## 关键结论的源码入口

| 结论 | 可复核文件 |
|---|---|
| 真实组合根与默认资源路径 | [bootstrap.cpp](../../src/server/bootstrap.cpp)、[main.cpp](../../src/main.cpp) |
| 当前 HTTP 查询装配 | [query_wiring.cpp](../../src/query/query_wiring.cpp) |
| chunk/doc/both、五路融合、源块还原、单 NS 重排 | [live_single_unit_executor.cpp](../../src/query/live_single_unit_executor.cpp) |
| gather 主要为排序去重截断，coverage 计算 | [scatter_gather.cpp](../../src/query/scatter_gather.cpp) |
| 实际入库阶段顺序和辅助 fail-soft | [spc_pipeline.cpp](../../src/spc/spc_pipeline.cpp) |
| PWL 而非跨库 ACID、推断提交、补偿恢复 | [write_coordinator.cpp](../../src/store/write_coordinator.cpp) |
| 向量日志先同步后更新图 | [phnsw.cpp](../../src/store/phnsw/phnsw.cpp) |
| Unit store/blob/memory 路径、恢复 adapters | [namespace_pool.cpp](../../src/resource/namespace_pool.cpp) |
| 页级 parse、取消边界、复用 post-parse | [document_processor.cpp](../../src/async/document_processor.cpp) |
| 上传只提交后台任务 | [upload_handler.cpp](../../src/upload/upload_handler.cpp) |
| MCP 直接 HTTP 和 identity 透传 | [transport.py](../../cortrix-mcp/src/cortrix_mcp/transport.py) |
| RAG retry/degrade/stream | [executor.py](../../cortrix-agent/agent_core/executor.py) |
| 聊天历史内存、10 turns | [session_store.py](../../cortrix-agent/agent_core/session_store.py) |
| Web fetch/CSRF 与上传的分支 | [client.ts](../../web/src/api/client.ts)、[routes.tsx](../../web/src/routes.tsx) |
| Quick Start 未启动 Agent/外部 LLM | [docker-compose.yml](../../deploy/docker-compose.yml) |
| 编译、依赖、SQLite serialized | [CMakeLists.txt](../../CMakeLists.txt)、[Dependencies.cmake](../../cmake/Dependencies.cmake) |
| 当前支持状态 | [compatibility.md](../../docs/compatibility.md)、[README](../../README.md) |

## 图的解释与限制

流程图为源码路径的手工归纳，不是编译器产出的精确调用图；可选框表示 gate/配置/依赖控制的路径。GC、memory 和可选 query 后处理属于模块级图，不断言每种 API 都按同一顺序执行。核心入库/query/恢复时序依据实现展开。

自动文件和 API 索引补全导航覆盖，不把所有索引条目称为逐行审阅。源码中的功能编号 Fxx/MEMxx 是历史设计标签，本目录用其辅助定位，不将编号推导为版本承诺。

## 建议后续验证入口

`tests/unit` 覆盖局部算法和协议，`tests/integration` 关注串联行为，`tests/scatter` 针对跨 NS，`tests/fault_inject`/`stability`/`fuzz`/`security` 提供故障和健壮性路径，`tests/benchmark`/`load`/`ragas` 分别对应性能/负载/评估。SDK、MCP、Agent、Skills 和 Web 各有独立测试。文件存在不代表测试已通过或达到生产保证。

本次交付检查由 [check_docs.py](../tools/check_docs.py) 离线验证本地链接、图源与图集同步、Mermaid fenced blocks、必需文件和 API 索引非空；该检查不代替 Mermaid parser/render 或运行时功能测试。


## Archify 重绘验证

2026-10-14 下载并使用 Archify 3.1.0 重绘 12 张图。JSON schema、源码路径/行范围、布局、HTML/SVG 产物与真实浏览器检查分别由官方 finalize 收据记录。每张图的最新结果以 [交互图集目录说明](../diagrams/archify/README.md) 和validation.json 指向的当前收据为准；浏览器检查与可选截图视觉审阅不可混为一谈。

本次安装和运行 Archify/Node/Chrome，不涉及启动 Cortrix 服务或下载其 ONNX 模型。普通上传来源 blob 的保存发生在 SPC 提交前；post-parse BeginWrite 明确 writes_blob=false，见 upload_handler.cpp:175–206 和 spc_pipeline.cpp:850–885。双层 GC 分别见 gc_manager.cpp 与 document_gc_sweeper.cpp。
