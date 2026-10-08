# P4 本地与上线门禁

## API error budget burn

这是 HTTP 服务处理可用性指标，目标暂设 99.9%，统计匹配路由的 5xx/全部请求，排除随机未知路由；4xx 不是服务器错误，但不代表业务成功。订单/库存一致性继续由独立校验器验证。

快窗口 5m + 1h 同时超过 14.4 倍预算，慢窗口 30m + 6h 同时超过 6 倍预算。短窗口至少 100 请求、长窗口至少 1000 请求，持续 2m。这些阈值只用于本地规则验证，生产目标需确认。缺失 series 不填零；无流量不等于达标。短历史也无法证明完整长窗口或 30 天 SLO 已达标。

先检查 Prometheus targets、业务审计新鲜度和 Collector/Tempo/Loki 状态，再按 service 查 5xx、延迟与依赖；在独立 Trace/日志页面定位。流量很少时使用 P3 的 TargetDown、WorkerNotReady、BusinessEvidenceStale 等告警，不依赖 burn-rate。

## 遥测故障

业务请求不得等待遥测重试。SDK 队列每进程 2048 spans、批 256、导出超时 1s。Collector 磁盘队列有限、重试最长 60s，故障超过预算可能丢数据，不能承诺无损。检查 trace_export_batches_total{result="failure"}、Collector failed/enqueue_failed spans、队列占用、磁盘与服务可用性；恢复后发一个显式 sampled 的验证请求，再从 Tempo 查到 trace。随机未采样 Trace ID 查不到是正常情况。

本地演练只操作独立 seckill-p4 项目，不停止当前业务项目。Collector/Tempo 停止演练验证业务不受阻及恢复后的新 trace 可查，不证明停机期间每条 trace 都补传。

## 性能预算不通过

保留所有 k6 原始结果与时间窗口。比较相同镜像、worker 数、缓存开关、CPU/内存限制和数据；至少三组交替运行，检查宿主机负载与 CFS throttling。通过减少采样、收敛 access logs 或合理调整资源预算进行后续实验时，须新增报告，不能覆盖失败证据或调整门槛来标记通过。

本地同宿主机结果只用于发现开销，不是容量承诺。发布前还需同构独立负载机、多轮长时间测量、真实对象存储/多节点 HA 与外部告警 firing/resolved 验收。
