# 生产准备模板

当前项目仅在本地运行。本目录没有部署到任何集群，不构成生产验收。

`collector-ha.yaml` 提供两副本 StatefulSet，每副本独立磁盘队列、资源限制、节点反亲和、PDB、mTLS、内部 Service 和入站 NetworkPolicy。先替换 StorageClass，创建包含 tls.crt/tls.key/ca.crt 的 collector-mtls Secret；证书 SAN 必须覆盖 Collector Service 和后端实际 DNS。业务 namespace 添加 observability-client=true 标签。SDK 使用 HTTPS 4318/v1/traces，并配置 OTLP CA/client certificate/client key 文件。不要把密钥提交到代码库。

该 Collector 使用无状态 head sampling 转发，可直接负载均衡。生产初始比例建议 10%，保持 ParentBased；这不保证所有错误均被采样。若改为 tail sampling，先使用 trace ID 路由把同一 trace 的所有 spans 发往同一采样实例；入口必须 100% 采集，并重新验收内存、decision_wait、长异步链路和故障转移。不能仅增加一个 tail_sampling processor 就声称保留所有错误。

后端生产拓扑必须另外部署并验收：

| 组件 | 拓扑与存储 | 起始保留预算 |
| --- | --- | --- |
| Prometheus | 两副本、独立 PVC、external_labels.replica 不同；告警发送前去掉 replica 标签；长期读取需要去重查询层 | 30 天，必须同时限定磁盘容量 |
| Alertmanager | 三副本 gossip 集群、每副本 PVC；三个地址均配置到 Prometheus，真实 webhook Secret 从密钥系统注入 | 30 天通知审计 |
| Tempo | 分布式 distributor/ingester/querier/compactor；ingester 三副本、replication_factor=3、WAL PVC；S3 兼容对象存储 | 7 天 |
| Loki | 分布式拓扑、三副本 ingester、replication_factor=3、WAL PVC；对象存储 TSDB、compactor 删除与保留开启 | 14 天 |
| Alloy | 每节点日志采集 DaemonSet、独立 positions/WAL；仅业务容器白名单；身份按集群 RBAC 收敛 | 不长期积压本地 WAL |
| 工作台 | 延用当前 UI 的监控、Trace、日志 sidebar；在访问入口接入统一认证及只读查询授权，后端信号接口保持内网 | 不公开当前无认证本地控制器 |

以上是部署约束，不是已生成并验证的 Tempo/Loki Helm values。选择目标集群和对象存储后，按实际 chart 版本生成 values，使用 server-side dry-run 检查；不要直接把本地 filesystem 后端扩为多副本。

资源、采样、保留、存储公式见 budgets.json。容量必须使用实际流量和压缩率校准，不能把日志输出字节视为 Loki 对象存储字节。数据库只读审计账号、最大连接数和网络访问范围沿用 P3 收敛配置。

上线前填写 acceptance.example.json 的每项检查及证据引用，然后执行：

```powershell
.venv/Scripts/python.exe performance/observability/go_live_gate.py --acceptance performance/config/production/acceptance.example.json
```

示例默认退出 2，生产环境、证据时间七天内、全部检查为 true、每项证据引用齐全才通过。这是验收清单门禁，不自动验证人工填写证据的真实性；发布流水线还应校验对应报告/演练记录并由环境负责人审核。

发布顺序为后端存储 → Collector → 日志采集 → metrics/rules → 少量业务实例灰度 → 工作台查询入口。回滚先将采样调低/关闭 tracing，保持错误日志和业务健康监测；再回滚 Collector/采集器，保留 PVC/WAL。不得因观测回滚清空业务数据库、Outbox 或 Kafka topics。

参考：[Google SRE 多窗口 burn-rate](https://sre.google/workbook/alerting-on-slos/)、[OTel gateway 与 trace 路由](https://opentelemetry.io/docs/collector/deploy/gateway/)。
