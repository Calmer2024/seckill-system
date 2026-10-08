# P0 指标契约

版本 0.1.0，2026-10-03。所有 duration 使用秒，timestamp 为 UTC Unix 秒；Counter 为进程生命周期累计量，Grafana/告警趋势使用 rate/increase。

| 指标 | 类型 | 标签 | 来源与含义 |
|---|---|---|---|
| http_requests_total | Counter | service、method、path、status | 四个 API；记录处理结果，保留既有名称 |
| http_request_duration_seconds | Histogram | service、method、path | 四个 API 的处理耗时；不是异步订单完成耗时 |
| product_cache_operations_total | Counter | operation、result | 既有缓存调用统计 |
| product_db_reads_total | Counter | operation、outcome | 既有商品查询操作统计；不等于物理 SQL 次数或主从路由次数 |
| seckill_requests_total | Counter | outcome | 既有订单受理/拒绝统计；不等于最终订单成功 |
| inventory_reservations_total | Counter | outcome、mode | 既有成功返回的库存预留统计；完整失败 outcome 覆盖留待后续阶段 |
| worker_task_alive | Gauge | role | 任务线程运行=1，未启动/异常退出/意外返回=0 |
| worker_loop_last_poll_timestamp_seconds | Gauge | role | 最近成功 poll（含空闲）或发送尝试完成时间；未发生=0 |
| worker_loop_last_progress_timestamp_seconds | Gauge | role | 最近已完成业务处理/持久化发布状态时间；未发生=0 |
| worker_task_failures_total | Counter | role | 未处理异常和意外返回次数；重启归零 |
| worker_ready | Gauge | 无 | 所有期望任务线程运行=1，否则0 |

API service 标签保持 user/product/order/inventory，target job 区分服务及实例。两个 worker 使用独立 registry，Prometheus target 标签 service=order-worker/inventory-worker、environment=local；不会把 API 的进程内业务 Counter 混进 worker 端点。

role 为代码定义的有限集合：order-outbox-publisher、inventory-result-consumer、payment-result-consumer、inventory-outbox-publisher、inventory-order-created-consumer。未知 role 拒绝登记。

HTTP path 只使用路由模板，404 未匹配归为 __unmatched__；method 允许 GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS/CONNECT/TRACE，其他统一 OTHER。/metrics、/health/live、/health/ready 不计业务 HTTP 指标及访问日志。

订单库存调用失败码映射为 out_of_stock、duplicate、product_not_found、stock_not_ready、inventory_service_unavailable、inventory_request_failed 或 other；既有 accepted 保持。自由字符串不得新增 outcome 序列。

禁止 ID、原始 URL、查询参数、搜索关键词、Redis key、自由文本异常成为 labels。实例定位使用 Prometheus target instance；日志及未来 span 承担订单/请求定位。

商品容器现有 PROMETHEUS_MULTIPROC_DIR 汇总四个 Uvicorn 进程，启动清理容器自己的临时目录；本阶段未新增 multiprocess Gauge/exemplar，不能据此宣称进程资源或 exemplar 支持。

采集新鲜度与 Counter 重启必须在查询时处理。进程业务 Counter 是趋势证据，不能替代数据库权威账本，也不能提供事务精确计费。P0 只增加 worker 健康；Outbox 实时积压、完整业务状态迁移、依赖连接池与最终一致性指标属于后续阶段。


## P1 追踪导出

`trace_export_batches_total{result="success|failure"}` 是 API 进程内异步导出的批次数，使用同一 prometheus-client registry（商品服务仍采用 multiprocess 汇总）。success 仅表示 SDK 导出请求成功，不保证 Tempo 持久化；未启用 SDK 或尚无批次时可能没有该序列，不能当作零故障。SDK 队列满会丢弃 span 并输出日志；本指标没有把队列丢弃计为导出失败，也不代表全量请求覆盖率。

Prometheus 新增 `otel_collector` 与 `tempo` jobs，组件端口可采集不等同于管道端到端成功。需要结合 Collector accepted/refused/sent/failed spans、sending queue 指标和实际 Trace ID 查询判断。


## P2 异步处理与状态迁移

共享包 0.3.0。订单/库存 API 使用进程 registry；worker 独立 registry 显式注册这些共享 collector，以及 trace_export_batches_total。

| 指标 | 类型 | 有限标签 | 定义 |
|---|---|---|---|
| event_publish_attempts_total | Counter | outcome=acked/failed | Kafka send 确认结果；acked 不表示 Outbox 状态提交成功 |
| event_process_total | Counter | role、outcome=processed/duplicate/failed | 完整处理与 offset commit 的结果；重复消息仍记录处理次数 |
| event_process_duration_seconds | Histogram | role | DTO/业务事务/Redis/offset commit 的总处理秒数 |
| event_offset_commit_failures_total | Counter | role | offset commit 抛出异常的次数；业务事务可能已提交 |
| business_state_transitions_total | Counter | entity、to_status | 真实状态变更且事务提交完成后增加 |

entity=order 的状态为 PENDING_INVENTORY/CREATED/FAILED/PAYING/PAID；entity=inventory 为 RESERVED/CONFIRMED/CANCELED。序列在首次事件后出现，空闲时不应把缺失序列解释为采集正常或已完成零笔业务。rate/increase 应保留 target service/instance 维度后聚合，不能将 API 与 worker 进程生命周期混为一份账本。

状态 Counter 无法与数据库事务原子提交；顺序重复消费不重复计数，进程提交后退出可造成漏计。查询库存、订单绝对数量仍需权威数据库采集。指标不携带订单、事件、用户 ID 或自由异常文本。现有压测范围 Outbox business exporter 未在 P2 改成环境级采集。
