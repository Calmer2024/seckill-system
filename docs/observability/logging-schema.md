# P0 日志与上下文契约

版本 1，2026-10-03。应用输出单行 JSON 到 stdout，统一服务日志和 Uvicorn 生命周期/错误日志；访问日志由共享中间件记录一次。

| 字段 | 契约 |
|---|---|
| schema_version | 1 |
| timestamp | 基于 LogRecord 创建时间的 UTC ISO 8601 |
| namespace | seckill |
| service | user/product/order-api/inventory-api/order-worker/inventory-worker |
| environment | OBSERVABILITY_ENVIRONMENT，默认 local |
| version | SERVICE_VERSION，未配置为 unknown |
| instance / process_id | 容器 hostname 或显式实例 ID；真实 PID |
| level / logger / message | 日志级别、logger 名称和脱敏消息 |
| event | 稳定事件名，保留已有业务 event 的兼容性 |
| request_id | 合法同步调用上下文；响应头及 httpx 下游传播 |
| trace_id / span_id | 预留合法内部字段，P0 不生成或存储 trace |
| route_template / method / status_code / duration_ms | HTTP 中间件输出；原始 URL 和查询参数不入 schema |
| order_id / product_id | 业务检索字段，不进入 metric labels |
| order_status / payment_status / from_status / to_status | 明确状态字段；不再由各服务 formatter 丢弃 |
| topic / group / partition / offset | Kafka 消费定位；逐消息上下文清理 |
| role / attempt / outbox_record_id | worker 任务、当前尝试、既有 Outbox 表记录 ID |
| event_id / causation_id | 预留；全局持久事件标识在 P2 实现 |
| db_role / read_database / write_database / page / size / count | 有限业务诊断字段 |
| outcome / error_code / exception | 处理结果及脱敏堆栈（保持 JSON 单行） |
| user_hash | 仅配置 LOG_USER_ID_HASH_KEY 后输出 HMAC；原始 user_id 不输出 |

ContextVar 在每个请求开始绑定、finally 清理。纯 ASGI 中间件保留同步线程池及流式响应上下文。外来 request ID 必须为 1–64 个允许字符，否则生成 UUID hex。Nginx 入口使用其自身 request_id，覆盖客户端任意 ID；直接服务调用允许传入经验证的 ID。

worker 消息记录 topic/group/partition/offset/order_id；持久化 Outbox 记录业务 ID 和原有表行 ID，P0 不虚构请求关联。consumer.process_failed 在消息上下文清理前记录；worker.task_exited 记录任务退出。失败 offset 不提交，P0 不自动重试或跳过。

不允许日志 schema 接收密码、JWT、Cookie、Authorization、请求体/响应体、keyword、cache_key 或原始 path。应用先遵守字段限制，formatter 对常见敏感模式再脱敏；未知无结构秘密无法保证被正则识别。新增字段要先更新 schema 与脱敏测试。

Nginx access log 使用独立网关 schema，带请求 ID、有限路由族、状态、上游地址/状态及秒级耗时。网关时间采用带时区的 ISO 8601。Nginx 原生 error_log 仍为文本，P0 没有宣称已实现集中采集或全部中间件统一 JSON。


P2 已激活 event_id、causation_id、trace_id/span_id 在 Outbox 发布和 Kafka 消费中的关联；新增 event.publish_acked、event.process_completed、business.state_changed 事件。outbox.publish_failed 与 consumer.process_failed 保留当前消息上下文。Event ID 为逻辑事件身份，重试保持；结果事件使用新 ID。元数据不包含业务 payload、用户原始 ID 或 baggage。
