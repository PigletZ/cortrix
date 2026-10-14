# Cortrix 源码架构分析导航

分析日期：2026-10-14。源码基线：`351f48958cc48bef47f35cf81d6809bc6a5be7a2`。版本文件：`1.0.0-rc.1`。

本目录由当前本地源码静态分析生成，重点核对入口、依赖装配、主 IO 调用路径和持久化边界；没有启动服务、下载模型或进行运行时性能验证。功能支持状态以仓库 `docs/compatibility.md` 与 README 为依据，不能从类名、测试文件或 OpenAPI 声明推导生产可用性。

## 阅读顺序

1. [系统总览与启动](architecture/01-system.md)：进程边界、配置、模块关系、部署。
2. [模块职责和接口](architecture/02-modules.md)：后端全部一级模块及外围工程。
3. [存储模型与恢复](architecture/03-storage.md)：NS/Unit、SQLite、向量索引、文件和 WAL。
4. [文档入库 IO](flows/01-ingestion.md)：上传、解析、分块、增强、清洗、持久化、异步。
5. [查询 IO](flows/02-query.md)：路由、fan-out、多路召回、重排、去重、降级。
6. [集成与运维 IO](flows/03-integrations-operations.md)：Web、SDK、MCP、Agent、memory、trace、GC。
7. [源码文件索引](reference/source-inventory.md) 与 [API 契约索引](reference/api-inventory.md)：用于逐文件和逐端点继续追踪。
8. [证据与验证范围](reference/evidence.md)：关键判断的源码入口和阅读限制。

## 架构图

优先打开 [Archify 交互图集](diagrams/archify/index.html)：12 张重绘的 HTML 图，覆盖总体架构、启动、入库、检索、查询时序、落盘、恢复、异步、Agent、接入、观测和 GC。各图旁保留 `candidate.json` 与校验收据，详见 [重绘说明](diagrams/archify/README.md)。

图表统一使用 Archify；修改各图的 `candidate.json` 后运行重绘脚本，生成 HTML 并更新校验收据。

## 归档原则

`architecture/` 存职责与数据模型，`flows/` 存输入输出和失败分支，`diagrams/` 存可编辑图源和图集，`reference/` 存证据与自动提取索引，`tools/` 存本目录的离线检查工具。分析与图表产物位于 `mydocs/`；下载的绘图运行工具位于 `.tools/` 并被忽略，未更改项目运行代码。
