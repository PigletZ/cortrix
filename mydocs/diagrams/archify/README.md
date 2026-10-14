# Archify 重绘版

优先打开 [交互式图集](index.html)。图集链接到 12 张独立 HTML，支持深浅主题、搜索/聚焦和查看器自带图像导出。直接用浏览器打开 HTML 即可，无需启动 Cortrix 或联网加载图表库。

| 图 | 类型 | 交互 HTML | 可编辑 JSON |
|---|---|---|---|
| Cortrix · 系统与模块架构 | architecture | [打开](01-system/01-system.html) | [图源](01-system/candidate.json) |
| Core · 启动装配与关闭 | workflow | [打开](02-bootstrap/02-bootstrap.html) | [图源](02-bootstrap/candidate.json) |
| 文档 · 入库与索引 IO | workflow | [打开](03-ingest/03-ingest.html) | [图源](03-ingest/candidate.json) |
| 查询 · 召回模块与 IO 架构 | architecture | [打开](04-query/04-query.html) | [图源](04-query/candidate.json) |
| 查询 · 跨 Namespace 调用时序 | sequence | [打开](05-query-sequence/05-query-sequence.html) | [图源](05-query-sequence/candidate.json) |
| Cortrix · 逻辑资源与物理落盘 | architecture | [打开](06-storage/06-storage.html) | [图源](06-storage/candidate.json) |
| 持久化 · SPC 写入与恢复 | sequence | [打开](07-write-recovery/07-write-recovery.html) | [图源](07-write-recovery/candidate.json) |
| F42 · 持久任务与解析进度 | workflow | [打开](08-async/08-async.html) | [图源](08-async/candidate.json) |
| Agent · 固定 RAG 与 SSE 时序 | sequence | [打开](09-agent/09-agent.html) | [图源](09-agent/candidate.json) |
| 接入 · MCP、SDK 与框架工具 | architecture | [打开](10-mcp-sdk/10-mcp-sdk.html) | [图源](10-mcp-sdk/candidate.json) |
| 运维 · 链路、健康与日志 | architecture | [打开](11-observability/11-observability.html) | [图源](11-observability/candidate.json) |
| 删除 · 双层 GC 与物理清理 | workflow | [打开](12-delete-gc/12-delete-gc.html) | [图源](12-delete-gc/candidate.json) |

## 安装与复现

使用 [tt-a1i/archify](https://github.com/tt-a1i/archify) 3.1.0，下载基线 `c21c31ffb879668900c5487ea24993bf45d89b15`。官方技能说明已读取并用于本次绘图；本地副本位于项目 `.tools/archify/SKILL.md`。Node.js 22.16.0 和 Chrome headless 安装在 `.tools/`；系统安装了 Chrome 所需动态库与 Noto CJK 中文字体。本地可执行工具被 `.tools/.gitignore` 排除，图表、JSON 和收据保留在 mydocs。

从项目根目录运行：

```bash
python mydocs/tools/render_archify.py
# 只重绘某张：
python mydocs/tools/render_archify.py 03-ingest
```

脚本调用官方 finalize，按 showcase 执行 validate → deliver → strict check → browser-check。发生错误时保留收据；它不会把失败退出当作通过。浏览器检查覆盖 1440×900、1600×1000、1920×1080、2048×1320 及深浅主题，视觉人工审阅是额外证据。[validation.json](validation.json) 汇总当前 JSON/HTML 与通过收据的哈希绑定，并指向每张图的有效收据；review-* 保留此前或重复检查证据。原目录的早期失败收据是历史记录，不代表当前图表状态。

## 阅读范围

系统和存储图按子系统聚合模块，细节由流程/时序图和配套模块文档展开。序列位置表达顺序，不是实测耗时；查询时序展开单 NS，其他 NS 并发执行。可选 LLM、sparse、rerank 与开发中能力的限制保留在节点、边标签或说明卡中。

图中分别说明普通上传 blob、SPC PWL 与两层 GC 的职责边界。新增和修改图统一维护本目录 JSON。

工作区新增或变更集中在 `mydocs/` 与 `.tools/`，项目业务源码未改动。源码证据绑定 Cortrix 当前 commit，而非未提交的分析文档。

查询关系图采用 architecture 模式；`04-query/authoring-history/workflow-draft.json` 是未通过的早期泳道草稿，保留用于追踪工具布局问题，不属于交付图源。最终调用顺序另见查询时序图。

12 张图全部通过自动验收；总体架构和查询图另有 [截图审阅记录](visual-review.md)。图表校验不代表 Cortrix 功能、性能或生产能力已验证。
