# P3 排障手册

适用当前本地环境。工作台监控、Trace、日志均为独立业务入口。先看采集时间与目标状态，再判断业务异常；没有数据不能当作没有故障。

## HTTP 错误 / 数据库连接压力

1. 监控页查看请求速率、延迟、MySQL 当前连接；Grafana API RED / Dependencies 看板查看受影响 service/instance。HTTP 错误规则至少需要两分钟内 20 个样本。
2. 日志按服务、ERROR、最近时间查询，使用 Request ID / Trace ID 查上下游。检查依赖超时、MySQL 1040、连接泄漏和 SQL 长事务。
3. 对照实例数、进程数和数据库连接上限。连接占用不是应用连接池等待的完整证据；当前未埋点池获取等待。不要直接增加上限掩盖泄漏。
4. 修复后确认连接回落、系统错误恢复，并收到 resolved 通知。低流量下不要用无样本 p95 判断改善。

## Worker / Kafka / Outbox 积压

1. 区分 target down、线程退出、轮询停滞和单纯没有业务进度。空闲轮询仍更新健康时间。
2. Messaging and Workers 看板查看有限业务 group/topic 积压、offset commit 失败与发布结果；Business Evidence 看板查看两类 Outbox 最老年龄。
3. 用 event_id / order_id / request_id 找日志，Trace 中查看 producer、consumer、业务事务和 commit。延迟 / 重试的 Span Link 可以跳转原始链路。
4. 确认 Kafka 可达、分区归属、反序列化 / 业务处理错误、DB 权限。排查 PUBLISHED 是否在 Kafka ack 后持久化。
5. 不要盲目修改 offset、删除 Outbox、重放支付或补库存。修复实际根因后确认 pending age、lag 回落且关键线程恢复。

## 负库存 / 等待库存订单

1. 先确认业务审计 collection_success=1，最后成功不超过 90 秒。否则先处理 BusinessEvidenceStale。
2. 全环境审计覆盖 order_db_0/1 的四张订单表、四张 Outbox 表，以及库存表和库存 Outbox。没有压测 product/user 范围。
3. 负库存表示 available/reserved/sold 任一列小于零。查询受影响商品的权威记录，按订单 / 事件日志定位对应状态迁移。该 gauge 不等于已证明库存守恒或跨服务对账完整。
4. PENDING_INVENTORY 最老年龄超过五分钟是延迟信号，检查两段 Outbox、consumer、Kafka 和库存结果处理。不能仅以最终成功订单为分母计算及时性。
5. 修复需要业务事务 / 幂等 / 补偿方案独立评审。观测系统不自动改库存或订单。

## 遥测缺失 / 日志丢弃 / Trace 导出失败

1. 监控 Telemetry Pipeline 看板与 Prometheus targets。检查配置加载、Docker 私网、磁盘空间和卷权限。
2. Alloy 只经 Docker GET 代理发现本项目的白名单容器。代理没有宿主端口，POST 禁止。检查 compose project 是否与 COMPOSE_PROJECT 一致；自定义 -p 时显式设置 COMPOSE_PROJECT_NAME。
3. Alloy positions 与 remote-write WAL 保存在 alloy_data；Loki WAL/index/chunks 在 loki_data。不要删除持久卷来“解决”重启问题。
4. WAL 保留上限一小时，写入队列 4MiB、batch 256KiB，失败退避最长十秒、最多 100 次；超过窗口、磁盘满或采集前 Docker 轮转仍可能丢日志。查看 dropped entries / retries 指标。Alloy WAL 在锁定版本中是实验特性，升级前必须重复恢复测试。
5. 只集中采集 JSON。Nginx stderr 的原始错误 / 启动文本不上传，避免原始 URL、IP 或凭据泄漏；必要时在本机受控查看。应用异常已经由共享 formatter 写为一条脱敏 JSON。
6. Loki 查询失败显示 503；Trace 未采样 / 已过期不代表业务没有发生。按 Request ID 或业务 ID 补充日志证据。
7. 恢复后验证新日志、积压重放和 trace 入库。业务请求不等待 Loki，SDK / Collector 使用异步有界导出。

## 业务审计过期

1. 检查 business-audit 目标、collection_success、collection_errors_total 和 last_success_timestamp。
2. 专用账号仅授予十张物理表 SELECT，最多两个连接；检查密码文件、MySQL caching_sha2 认证、表布局、超时和权限。不要改成长期 root 采集。
3. 每轮使用单一主库 InnoDB REPEATABLE READ 只读一致性快照。每条 SELECT 最大执行两秒，连接两秒、读写三秒，成功 / 失败后休眠三十秒。
4. 全部查询成功才原子替换证据；失败保留最后成功时间，绝不补零。持续超时应调整扫描索引 / 账本聚合与预算，不能把扫描频率拉高。

## 告警通知失败

1. 工作台监控中的活动告警和通知记录分别查询 Alertmanager 与接收器，不混淆 rule firing 与实际送达。
2. 检查 Alertmanager notifications_failed_total、接收器 /health、/metrics 和 SQLite 卷。接收器在事务提交后才回 200；存储不可用返回 503 供 Alertmanager 重试。
3. 按 environment/service/alertname 分组。Worker target down 对相同 instance 的 task-down / loop-stalled 做抑制。工作台默认列出未静默、未抑制的活动告警。
4. 本地持久通知去重并保留七天、最多一万条；firing / resolved 分开保存。进程重启后应仍可读取已接收记录。
5. 目前实际投递渠道是本地工作台。生产 IM / 邮件 / 值班渠道需配置实际接收人、凭据和端点，再验证触发与恢复，不把本地验收当成外部送达。
