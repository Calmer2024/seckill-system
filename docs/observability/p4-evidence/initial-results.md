# P4 本地隔离实测

范围：local isolated read-only catalog; 4 VUs; cache disabled; same image and limits
商品接口 GET /api/products，4 个 Uvicorn 进程，4 VUs；每轮 20 秒，三组交替比较。此结果不是生产容量或 HA 验收。

| 轮次 | 请求 | RPS | P95 ms | P99 ms | 平均 CPU 核 | 末尾内存 MiB | 日志输出 B/请求 | 错误率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| cold-off | 5688 | 284.33 | 77.93 | 79.37 | 0.932 | 321.9 | 0.0 | 0.00% |
| cold-on | 5289 | 263.76 | 78.36 | 79.44 | 0.940 | 331.2 | 1106.6 | 0.00% |
| pair-0-off | 5631 | 281.50 | 73.04 | 82.04 | 0.944 | 330.0 | 0.0 | 0.00% |
| pair-0-on | 5301 | 264.08 | 78.36 | 79.36 | 0.940 | 332.6 | 1106.6 | 0.00% |
| pair-1-on | 5297 | 264.46 | 78.52 | 79.61 | 0.941 | 333.7 | 991.1 | 0.00% |
| pair-1-off | 5720 | 285.03 | 78.05 | 79.18 | 0.942 | 326.2 | 0.0 | 0.00% |
| pair-2-off | 5697 | 284.00 | 77.96 | 79.31 | 0.940 | 327.4 | 0.0 | 0.00% |
| pair-2-on | 5286 | 264.27 | 78.48 | 79.47 | 0.941 | 333.9 | 1106.6 | 0.00% |
| collector-unavailable | 4814 | 240.31 | 78.86 | 80.41 | 0.945 | 338.6 | 859.0 | 0.00% |

配对吞吐损失中位数：6.95%。配对 P95 增幅中位数：0.67%。
5% 开销门禁：未通过。生产门禁：未通过。

CPU 取 cgroup usage_usec 增量 / 执行墙钟时间（含 k6 启动与收尾），内存为 cgroup memory.current；峰值另见 JSON。日志字节为 docker compose logs 的 UTF-8 输出，含 Compose 前缀，不是 Loki 压缩存储成本。
冷状态指进程重启后的首次负载，缓存关闭；数据库 buffer pool 与宿主机页缓存未强制清空。off 关闭共享 HTTP 遥测、SDK 导出和 INFO 日志，保留请求上下文、框架已有 Trace ID 及既有业务计数器。
on 使用 10% ParentBased head sampling。预算化与 hotpath 试验对成功且未采样请求的 access log 再抽样 10%；错误/拒绝、已采样 Trace 的关联日志与业务状态日志全部保留。hotpath 把商品成功 DB 读取日志降为 DEBUG，计数器和 Trace 保留。各轮镜像及策略不同，原始结果均保留。
这里测量应用侧观测开销与异步 Trace 导出，没有为隔离项目接入完整 Prometheus/Alloy/Loki 链路，不代表整个观测集群的资源开销。宿主机同时运行原业务与 P3 组件，噪声尚未隔离；20 秒试验不能替代长时间稳定性测试。

## 故障与契约

```json
{
  "fault": {
    "business_available": true,
    "trace_recovered": true,
    "recovered_trace_id": "a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4"
  },
  "contracts": {
    "random_404_paths": 100,
    "unmatched_metric_series": 1,
    "bounded_route_cardinality": true,
    "restart_clears_old_multiprocess_counters": true,
    "requests_before_restart": 26089.0,
    "requests_after_restart": 1.0,
    "database_unavailable_http_status": "503",
    "database_fault_visible": true,
    "database_recovered": true
  },
  "gates": {
    "measurement_complete": true,
    "zero_http_errors": true,
    "median_rps_loss": 0.06947602324046154,
    "median_p95_increase": 0.006653059990737731,
    "overhead_within_5_percent": false,
    "fault_isolation": true,
    "cardinality_and_restart": true,
    "database_fault_and_recovery": true,
    "production_ready": false,
    "production_blockers": [
      "No production cluster validation",
      "No real external alert delivery validation",
      "Local shared-host performance is not a production capacity result"
    ]
  }
}
```

恢复后新 Trace 可查不等于停机期间无丢失。SDK 超出有界队列会丢弃；初轮未专门计数 overflow 日志，预算化轮次记录的 overflow_messages 只覆盖本轮仍可读取的日志。没有进行磁盘耗尽、对象存储故障、多节点切换或外部通知验收。

JSON、逐轮 k6 原始结果与 Docker 资源数据为验收依据。生产验收仍需要同构环境、真实通知渠道、认证、保留恢复与多节点演练。
