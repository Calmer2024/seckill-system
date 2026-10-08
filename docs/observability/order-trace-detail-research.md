# 订单执行详情对照 LangSmith 的研究

研究日期：2026-10-08。依据为本轮用户截图、LangChain / OpenTelemetry 官方文档、当前代码以及本地真实订单只读查询。本轮形成设计结论，不修改运行实现。

## 1. LangSmith 的组织方法

官方概念说明中，Run 是一次操作，可类比 OpenTelemetry Span；Trace 组织单次执行的 Run 树；Thread 按会话组织多个 Trace，保留各自嵌套结构。Trajectory 将会话投影为顺序消息视图。

来源：[Observability concepts](https://docs.langchain.com/langsmith/observability-concepts)、[Configure threads](https://docs.langchain.com/langsmith/threads)。

截图直接可见的交互：左侧按编号排列执行轮次，轮次内嵌子节点，提供搜索、折叠和 Waterfall 入口；节点显示类型图标、耗时和辅助指标。选中节点蓝色高亮，右侧切换该节点的 Input、Output、Attributes，字段分组可折叠。截图只能证明 Waterfall 入口存在，不能据此断言其所有交互行为。

可借鉴的核心是同一面板内的“执行索引 + 完整调用树 + 所选节点详情”，无需把用户不断带到另一个详情层。

## 2. 秒杀系统的对应关系

| LangSmith | 本平台 | 语义 |
| --- | --- | --- |
| Thread | Order Journey / Orders 详情 | 按 order_id 聚合多个执行，不等于一个巨大 Trace |
| Turn / Trace | 一次下单、付款或后台任务执行 | 按开始时间排序，保留独立 Trace ID |
| Run | Span | HTTP、业务函数、数据库、缓存、消息操作 |
| Trajectory 的阅读视角 | 订单业务时间线 | 依据状态事件与执行证据阅读业务进程 |

不同 Trace 的时间先后只表示观察顺序。调用父子关系由 parent_span_id 支持；跨 Trace 的消息因果关系使用 Span Links、event_id、causation_id 等证据。不能只按时间把付款挂为下单的子调用，也不能把当前订单状态当作每个历史节点的执行结果。

来源：[OpenTelemetry Traces](https://opentelemetry.io/docs/concepts/signals/traces/)、[Messaging spans](https://opentelemetry.io/docs/specs/semconv/messaging/messaging-spans/)。后者明确区分父子关系与消息关联链接。

## 3. 当前实现的具体缺口

检查位置：`performance/web/trace-orders.js` 的 buildNodes / renderTree / renderNode，以及 `performance/web/traces.py` 的 trace_lifecycle。

- 已有订单根容器、Trace 分组、Span 子树、搜索、折叠、详情选项卡和单 Trace 跳转，具备继续改造的基础。
- lifecycle 的 timeline 仅保留直接带查询订单标识的 Span。没有该属性的 HTTP 父节点、数据库或缓存子调用被过滤，树可能断裂。真实样本关联到 3 个 Trace，完整调用分别有 4、23、29 个 Span，共 56 个，而订单 timeline 只返回 15 个。
- Trace 分组来自匹配节点首次出现的顺序，没有显式用 Trace 根开始时间建立序号；缺少醒目的开始时间、耗时、结果与并发/异步关系标识。
- 有跨 Trace 链接、事件和重试字段，但左侧树未充分利用。此次样本的 15 个匹配节点没有 Span Links，这不证明其他订单也没有。
- 点击步骤虽能切换右侧，但它使用裁剪后的订单节点字段，进一步查看完整 Span 需要另开 Trace 面板。应在订单面板中直接读取完整节点详情。
- 当前查询有最多 20 个 Trace、300 个订单匹配节点的边界，需要持续显示截断、不可用和缺失证据提示，并设计后续加载能力。

## 4. 推荐落地方案

1. 用订单标识发现相关 Trace，再读取各 Trace 完整树。完整树保留父节点；对可能包含批量或其他订单的分支注明上下文范围，默认突出本订单命中节点，不能把所有节点都标为本订单业务步骤。
2. 左侧以每次执行为一级条目，按根开始时间排列并编号。展示可验证的入口名、服务、时间、耗时、结果；业务名称由已知路由或业务操作映射，未知执行保留原始名称。
3. 展开后根据 parent_span_id 展示完整 Span 树，同级按开始时间排序。父节点缺失、孤立节点或异常循环明确处理。订单记录和 Outbox 证据保留独立数据来源标识。
4. 点击 Trace 显示执行摘要；点击 Span 在同一右侧区域显示完整 Input、Output、Attributes、Events、Links 和日志入口。所选 trace_id / span_id 写入 URL，刷新、返回和复制链接都能定位原节点。
5. 提供 Tree / Waterfall 切换。Waterfall 使用实际起止时间表达并行、重叠和等待；订单创建至付款的墙钟时间与服务执行耗时分别标注，不简单相加嵌套 Span 耗时。
6. 有证据的消息发布、消费、重试使用关联标识或链接展示。缺失事件或未采样执行显示证据缺口，不补造完成步骤。

优先级：先修复完整树数据与排序，再完成同面板节点详情和 URL 恢复，随后增加 Waterfall 与跨 Trace 因果导航。

## 5. 实现与验证记录

2026-10-08 已实现完整执行树、按时间编号、节点类型色、同面板详情、URL 恢复、按 Trace 独立刻度的分组 Waterfall（逐项折叠、缩放、重置）、Span Links 跳转、关联日志及返回。接口保留原匹配 timeline，以 executions.spans 承载安全上下文，每个节点通过 identifier_match 区分是否直接匹配订单。

真实订单验证从 15 个订单匹配节点扩展到 56 个关联执行节点。跨执行 Span Link 跳转使用显式测试样本验证，不能据此认为真实订单已经具备所有消息因果证据。每条执行最多返回 200 个节点，并显示截断；完整性仍取决于采集、采样、保留与查询范围。

验证脚本：`tests/observability/order_investigation_check.py`；结果：`docs/observability/order-investigation-validation.json`。
