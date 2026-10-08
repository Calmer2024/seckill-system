# 独立压测控制台

压测平台作为独立的本地控制器运行，不接入商城 React 前端，也不会修改商城页面的路由和布局。

## 启动

在仓库根目录执行：

```powershell
./performance/web/start-web.ps1
```

该命令以前台方式运行，关闭当前终端后控制器也会停止。需要让控制器在后台运行时使用：

```powershell
./performance/web/start-web.ps1 -Background
```

然后打开 `http://127.0.0.1:8099`。启动脚本会先检查健康接口，确认控制器真正监听成功后才返回。控制器默认只绑定回环地址，页面、API 和报告文件都由同一个 Python 进程提供。

## 工作区界面

侧栏包含“压测”“监控”“Trace”“日志”四个独立业务入口。压测工作区左侧是运行列表和搜索、状态、场景、模式筛选；点击列表项后，右侧切换到该任务的详情。详情包含“报告”“压测指标”“业务校验”“运行日志”四个视角，共用同一任务上下文。标题区的“新建任务”打开配置弹窗，并实时展示提交摘要。

页面入口是 `#runs`。查询参数 `run` 可直接选中任务，`view` 选择 `report`、`metrics`、`validation` 或 `run` 详情视角；`q`、`status`、`scenario`、`mode` 保留列表筛选。刷新页面后可恢复当前上下文。

“压测指标”展示所选报告的指标快照；“业务校验”展示报告自带的一致性规则结果。环境指标和告警在独立“监控”页，追踪与集中日志在独立侧栏页面。当前没有数据集、评估器或实验服务。中文字体优先 PingFang SC，英文使用本地 Inter Regular；图标采用 Lucide SVG。详细规范见仓库根目录 `Style.md`。

## 能力

- 选择 `product-read`、`seckill-contention`、`traffic-spike`、`stability-soak` 场景
- 切换 `distributed` 和 `baseline` 模式
- 配置商品、库存、用户范围、数据重置、镜像构建和 Prometheus 采集
- 通过现有 `performance/run-test.ps1` 启动压测，保留 `-ConfirmTarget` 授权保护
- 查看运行状态、当前阶段、控制器日志和历史运行记录
- 直接解析 `report.json` 展示负载、业务结果、业务一致性、可观测性和策略对比
- 下载 JSON / CSV / HTML / 校验文件

## API

- `GET /api/performance/health`
- `GET /api/performance/scenarios`
- `GET /api/performance/runs`
- `POST /api/performance/runs`
- `GET /api/performance/runs/{run_id}`
- `GET /api/performance/runs/{run_id}/report`
- `POST /api/performance/runs/{run_id}/stop`
- `GET /api/performance/runs/{run_id}/files/{filename}`

启动请求必须包含 `confirm_target: true`。控制器只允许 `frontend_nginx` 和 `host.docker.internal` 作为目标入口，避免网页表单被当作任意远程流量代理；其中前者是 Compose 内网网关，后者用于被测服务运行在宿主机的情况。
# P0 可观测接入

可观测能力共用本工程工作台，但在独立侧栏页面中展示。监控显示当前环境时间序列、worker 健康、活动告警和通知；Trace 与日志各自提供独立查询。压测详情仅展示所选任务的历史指标。

接口为 `GET /api/performance/observability/status`。已有控制器需重启以加载新增后端路由；完整配置、更新与排障见 [P0 运行说明](../../docs/observability/p0.md)。


### P1 同步追踪

独立 Trace 页面提供分布式追踪查询与调用瀑布，可按服务、最近时间、最短 span 耗时、错误 span 筛选，或用响应头 / JSON 日志中的 Trace ID 定位。列表是本地环境当前的采样链路，不属于所选历史报告。

使用 `docker-compose.observability.yml` 启动 Collector 和 Tempo；`run-test.ps1 -WithMonitoring` 自动添加该文件。当前环境为 baseline 时，同时保留 `performance/config/docker-compose.baseline.yml`。只读 API 为 `/api/performance/observability/traces` 和 `/api/performance/observability/traces/{trace_id}`，不接受任意查询语言或后端地址。详见 [P1 部署、故障隔离与验证说明](../../docs/observability/p1.md)。


P2 分布式追踪扩展：独立「Trace」页面可筛选 order-worker/inventory-worker、订单 ID 和事件 UUID，查看 Kafka 发送/消费 span 与重试/延迟 Span Link，并点击关联链路跳转。数据仍为本地实时环境；历史任务选中不代表 trace 属于该次 run。详见 `docs/observability/p2.md`。


当前页面结构：侧边栏「压测」(`/#runs`)、「监控」(`/#monitoring`)、「Trace」(`/#traces`)、「日志」(`/#logs`) 共用前端外壳。监控与 Trace 不要求运行记录，不依赖压测任务。压测详情的「压测指标」只展示选中 run 的历史快照。环境查询使用 `/api/observability/*`，压测操作继续使用 `/api/performance/*`。

P3 已接入 Alloy/Loki、Alertmanager 和持久通知接收器、全环境只读业务审计，以及工作台内时间序列与日志关联。新 API 为 `/api/observability/logs`、`/api/observability/metrics`、`/api/observability/alerts`。初始化专用审计账号与配置文件后部署，详见 [P3 运行与验证说明](../../docs/observability/p3.md) 和 [排障手册](../../docs/observability/p3-runbooks.md)。外部通知渠道与生产高可用尚需部署配置。

P4 增加独立监控页的 HTTP 错误预算图，以及压测报告的观测边界快照、真实响应关联样本和 k6 日志下载。观测业务仍不依赖压测 run。隔离验收、测量限制与生产门禁见 [P4 说明](../../docs/observability/p4.md)。

工作台图标统一使用项目 LangSmith 风格规范中的 Lucide SVG（`icons.svg`），不使用 Unicode 或 emoji 作为功能图标。`controls.js` / `controls.css` 统一下拉列表、复选框、折叠箭头、输入框、滚动条、提示和行内校验样式。下拉框支持方向键、Home / End、Enter、Escape 和 Tab，隐藏的原生字段保留原查询参数与表单语义。新增前端控件时应复用这些组件，避免重新引入浏览器默认控件外观。


## Trace 浏览与调查

Trace 页面以 LangSmith 截图为参考，采用分面筛选、紧凑记录表和右侧详情面板。点击记录保留列表上下文，同时展示可折叠的执行链路树和所选节点详情。支持当前结果内搜索、最新/耗时排序、全部展开/折叠、节点搜索保留祖先、Waterfall、详情宽度切换和 Escape 关闭。

详情提供概览、Input、Output、Attributes、关联链路、耗时、事件、运行环境和生命周期视角。Input/Output 是已采集的结构化上下文，当前采集器没有导出请求与响应正文。列表自动补全接口结果、业务状态、商品/订单标识与摘要；原始 Span UNSET 不会被改写为 OK。HTTP 202 显示已受理，订单最终结果单独展示。

`?trace={traceId}&span={spanId}&trace_tab=overview|input|output|attributes|links|analysis|events|runtime|lifecycle#traces` 可恢复详情上下文。延迟或重试的 span link 可打开目标链路及节点，关联日志查询使用链路发生时间。缺失父节点作为独立分支展示，异常父关系不会造成树无限递归。

实现位于 `trace-explorer.js` / `trace-explorer.css`，复用现有控件与图标。查询保留 Tempo 的环境隔离、字段白名单及 50 条记录 / 1000 span 上限；展开在浏览器内渐进展示，不代表后端分批加载。

验证命令（在已有测试环境中执行）

```powershell
./.venv/Scripts/python.exe -m unittest tests.observability.test_traces -v
# 需要 Playwright 和 Chromium；默认对 8100 端口控制器运行，也可设置 TRACE_UI_URL
python tests/observability/trace_ui_check.py
```

浏览器验证通过请求拦截使用测试 fixture，不将模拟记录加入生产接口。


### LangSmith 内容页布局与查询控件

Tracing 采用统一字段搜索、时间/视图工具栏和分面宽表，移除次顶部项目导航，侧栏背景为 `#fafbfd`。Trace 页面不再显示介绍式大标题；浏览器主体不滚动，筛选、表格、链路树、节点详情分别在自己的区域内滚动。设计 Token 收束到 `trace-explorer.css` 的 `--tx-*` 变量，主蓝为 `#006ddd`，选中背景为 `#e5f4ff`，分隔线为 `#e2e8f0`，控件以 32px 高度与 5px 圆角为基准。

`trace-controls.js` 提供全部时间选项：Last 1/3/6/12 hours、Last 1/2/7/14/30 days、All time、相对时间（例如 15h、90m）以及 Choose dates。默认时间可保存到此浏览器。相对时间支持 1 分钟到 30 天；自定义日期使用本地时间并发送 Unix 秒。查询选项不会延长数据保留期，当前仓库配置为 24h。

14/30 天等范围按不超过 7 天的查询块合并、去重，避免 Tempo 默认单次查询时间上限；All time 从 Tempo 当前有效 compactor 配置读取保留期，只查询仍保留的历史数据。长于 30 天的自定义范围也与保留窗口相交，响应同时返回请求范围和有效起点。配置不可读、部分分块失败均返回查询失败，不伪装成完整的空结果。

字段补全和运算符建议支持方向键、Enter、Escape。查询格式是 `field:value` 或 `-field:value`，含空格的值用双引号，例如 `name:"POST /api/orders" -service:user`。字段包括 name、service、status、method、route、db_system、topic、outcome、error、trace_id、order_id、event_id；纯文本按名称包含查询，直接粘贴 32 位 Trace ID 可定位详情。in root run / in all spans 控制名称和服务匹配粒度，其他协议与业务条件匹配已采集的 span 字段。当前未采集的正文、附件不会作为可查询字段提供。

后端将有限字段语法翻译为转义的 TraceQL，不接受任意 TraceQL。字段映射依据 [Tempo TraceQL 官方文档](https://grafana.com/docs/tempo/latest/traceql/construct-traceql-queries/)。Save View / Views 在此浏览器保存时间、查询、分面、排序与可见列。查询 URL 包含 `trace_range`、`trace_start`、`trace_end`、`trace_query`、`trace_query_scope`、`trace_filters`、`trace_sort`、`trace_columns`，刷新后恢复时间、字段查询、分面、排序与可见列。

链路树、节点详情和筛选栏的折叠使用 180–190ms 过渡，遵循 `prefers-reduced-motion`。折叠期间隐藏内容禁止键盘访问，快速反复操作会取消旧的关闭计时器。关联链路提供返回上一条链路操作，并恢复所选节点、详情页签、折叠状态和树滚动位置；跳转日志后可返回当前调查。详情支持相邻请求导航，空结果可重置，查询失败可重试，结果达到 50 条上限时提示缩小范围。字段语法、日期范围和存储失败均提供具体反馈。

`icons.svg` 使用官方 Lucide 1.53.0 的 24px SVG 路径，统一 2px 描边，使用 `python performance/web/build_icons.py` 从固定版本的官方 `lucide-static` 包生成，许可见 `LUCIDE-LICENSE`。商城使用同版本 `lucide-react`，平台仅使用 Lucide。复选框白色勾选 SVG 以控件中心定位；查询键盘提示、日历和折叠箭头也来自同一图标库，不使用文字符号作为图标。

列表不把 Tempo 搜索摘要当作完整请求数据。首批记录返回后，以最多 4 个并发调用 `/api/observability/traces/{id}/summary` 渐进补全状态、Input 和 Output；换查询或离开页面会取消旧请求，失败摘要显示重试提示。服务端摘要缓存 20 秒、最多 100 项。Input 使用已采集的 HTTP 方法、模板路由、数据库或消息操作；Output 使用 HTTP 状态码、业务结果与业务代码，正文仍未采集。2xx/3xx 或明确业务 success 才显示成功；4xx/业务 rejected 显示业务拒绝；错误 span、5xx 或业务 error 显示技术错误；缺乏结果证据保留未知。HTTP 404 的业务拒绝不再显示成成功勾选。

### 秒杀业务调查

追踪工作区提供 Orders、Traces、Spans、Services 四种视角。Orders 使用与 Traces 相同的搜索、时间选择、左侧筛选、局部滚动表格与双栏详情抽屉；默认读取最近订单，支持订单号、状态、商品和创建时间筛选。按 Snowflake 订单编号从新到旧排序，每页 50 条；通过 `before` 游标跨四个物理分片合并分页，不用 OFFSET，也不暴露用户身份或金额。URL 保存 `trace_view=orders`、`trace_order` 和 Orders 筛选条件，旧 `journeys` 链接兼容打开 Orders。

点击订单行展开订单详情：左侧为订单当前状态、Outbox 事件、关联 Trace 和可折叠的执行节点树；右侧为所选步骤的概览、Input、Output、事件、Attributes。采样节点按可用父子关系嵌套，缺失父节点作为独立分支展示。跳转 Trace 可进入指定 Span，并通过“返回订单”恢复原订单步骤和列表位置。数据库状态与采样执行证据分别注明来源。

本地 `.env.observability.local` 已启用 `SECKILL_TRACE_SAMPLE_RATIO=1.0`，用于手工验证下单/付款的新链路；Compose 和生产配置默认策略不变。100% 采样不保证缺少埋点或导出失败时链路完整，也不能恢复历史遥测。

订单当前状态由 `business-audit` 的 SELECT-only 账户读取主库四个物理订单分片，在同一个只读一致性快照内查询订单和 Outbox。内部 HTTP 接口只映射到本机 `127.0.0.1:9124`，控制器通过固定地址代理；不读取用户 ID、金额、消息 payload 或敏感正文，不借用业务服务数据库凭据。当前状态不受 Trace 时间范围或采样影响；Outbox 最多返回 25 条。数据库不可用、订单不存在、分片冲突和 Tempo 不可用分别显示，Tempo 故障时仍返回数据库状态。

当前订单表只保留当前状态及创建/更新时间，Outbox 也不是完整的状态审计日志。因此页面不能还原未持久化的全部状态变更。数据库快照中的 PAID 不意味着当前时间范围一定存在付款 Trace。历史未采样、过期或缺少埋点的链路无法补回。

Traces 摘要显示入口执行类型（API、消息、后台任务）、涉及的服务及节点数。执行类型筛选在当前最多 50 条结果中应用；Spans 和 Services 复用已读取摘要，每条最多 200 个节点，并提示截断和摘要读取失败。服务关系统计仅根据采样样本中的直接父子调用，不能用作全量 RED 指标或全局服务拓扑。

`python tests/observability/trace_journey_check.py` 检查本地最近订单列表、真实数据库状态、订单与真实 Trace/Span 的跳转返回、URL 恢复、局部滚动和移动端布局；分页、后端故障和恢复另外使用浏览器测试夹具。该检查不会创建订单或执行付款。

`method` 和 `db_system` 查询兼容新旧 OpenTelemetry 字段。否定条件只匹配实际存在的对应字段，避免字段缺失时误判或把所有请求过滤掉。新 Trace 详情与搜索索引可能在不同时间可见；真实验证按 Trace ID 收窄范围并等待索引，避免 50 条结果上限造成误判。

`python tests/observability/trace_soak_check.py` 运行三分钟持续观测，覆盖真实读取、秒杀拒绝、四个服务健康检查、协议字段查询与采样详情校验。报告保存在 `docs/observability/trace-soak-validation.json`；不重置数据、不改变采样配置。

本地 Tempo 使用 1GiB 容器额度和 768MiB Go 内存软上限，查询执行并发为 4、单个搜索任务并发为 8，避免默认查询并发在小内存容器中触发 OOM 重启。可用 `TEMPO_MEMORY_LIMIT` 和 `TEMPO_GO_MEMORY_LIMIT` 调整额度，Go 软上限应低于容器额度。原 512MiB 配置在持续观测中出现过 Docker OOM 事件和短暂查询 503；调整后需通过持续观测确认稳定性。

业务埋点按白名单记录商品、数量、订单、请求 ID 和实体状态，不序列化 DTO 或用户身份。消息处理展示 Event/Causation ID、重试次数、分区、偏移和消息等待估算；业务状态提交、处理完成和消息确认事件在导出前脱敏，异常正文与堆栈继续排除。运行环境展示版本、实例和环境；优先使用发布版本，其次使用构建源码指纹；两者都缺失时显示 unknown。

镜像构建时自动计算应用与埋点源码指纹，作为未配置发布版本时的 `service.version`（`source-sha256:…`）；显式发布版本优先，`unknown` 不再覆盖构建指纹。日志使用同一版本来源。商品、库存、订单列表/详情和支付入口提供业务节点，入口 Span 在响应开始前写入路径标识和接口结果，避免响应结束后写入失效。列表采集返回数量，商品查询采集分页，库存详情采集可用/预留/售出库存；不导出列表中的用户身份。SQL 导出归一化后的查询指纹，不导出语句或参数。

列表、详情中的业务状态区分不适用的读取操作、本次未创建订单和未采集字段。拒绝请求不会编造订单状态；依赖 Span 不会被当作订单节点。新增字段仅覆盖部署后的采样请求，历史 Trace 无法追补。`python tests/observability/trace_collection_live.py` 验证真实网关、业务服务、SQL 指纹、版本及 Order ID 生命周期关联，不重置数据，也不改变网关采样配置。

耗时面板以直接子节点时间区间并集计算自身耗时，分别展示入口响应时间、所观测节点跨度、服务耗时汇总与可跳转的慢节点。自身耗时包含等待，不能等同 CPU 时间；并行节点总和不能作为端到端响应时间。该视图提供瓶颈定位，并不声称还原完整关键路径。

生命周期按 Order ID / Event ID 和当前时间范围关联最多 20 条 Trace、300 条节点，详情最多四并发。上限、不可用详情和采样限制均展示，点击节点保留原调查的返回路径。业务数据库是订单当前状态的权威来源。当前入口覆盖后端 API；浏览器与网关等待、未采样请求不在链路中。旧数据不会补出新埋点。产品、活动、请求标识、业务状态、版本、实例和 Causation ID 支持字段查询；活动字段只有业务对象实际提供时才采集。

按钮使用共享的 Lucide 操作映射，动态详情也应用同样规则。工具栏、分段导航和详情按钮外部高度为 32 px，单图标操作无背景/边框/阴影，保留悬浮和焦点提示、无障碍名称；导航、记录及关键业务操作保留文字。商城同步改为本地打包的 `lucide-react` 图标。

监控、日志和压测复用 Trace 的视口布局、局部滚动、筛选表格与双栏详情。监控包含 Dashboards / Alerts / Services，图表按 HTTP、Dependencies、Business、SLO 分类；可切换真实指标数据表并放大查看最多 16 × 121 个数据点。指标和日志时间预设支持 1/3/6/12 小时、1/2/7/14/30 天，仍受 Prometheus/Loki 实际保留期限约束。日志正文、服务、级别、关联标识查询保持白名单与脱敏；查询最多 200 条。Spans / Services 只汇总当前最多 50 条 Trace，每条最多 200 个摘要节点，详情与 Trace 可互相调查。压测列表点击打开报告面板，新建/停止任务表单及确认流程保持可用。

### 工作区查询与布局

监控、日志和压测不再使用次顶部标题栏，查询框和工具栏直接位于可点击的面包屑下面。页面保持局部滚动；监控恢复双列图表，压测报告使用指标网格和校验表格。压测详情取消内部侧栏，任务编号、场景和状态集中在顶部左侧，窄屏自动换行。

- 日志查询支持 `service:order-api level:ERROR trace_id:… order_id:… event_id:… request_id:… text:"正文关键词"`，也可直接输入正文关键词。左侧仅提供服务和级别标签，同一分组选择一个条件。
- 压测查询支持 `status:completed scenario:… mode:baseline run_id:…`，普通文字匹配任务编号及场景；标签与搜索条件同步，未知字段或无效值明确提示。
- 订单查询支持直接输入订单编号，或组合 `order_id:… product_id:… status:PAID`；左侧保留订单状态标签。
- Trace 的左侧保留服务、入口、错误及耗时阈值标签，订单和事件编号使用顶部字段查询。
- 监控搜索过滤当前采集数据中的指标、告警或服务，时间范围仍决定实际后端查询。
- 日志 DEBUG / INFO / WARNING / ERROR / CRITICAL 分别使用灰、蓝、橙、红、紫色，始终保留文字级别。

### Orders 执行详情

订单详情左侧按实际开始时间编号排列关联 Trace，展开后保留调用父子结构。节点显示类型、服务、时间、耗时；数据库、消息节点使用统一 Lucide 图标和类型色。直接匹配订单标识的 Span 与完整 Trace 中的上下文节点分别标识，业务数据库快照与 Outbox 证据保留独立来源。

点击 Span 在订单面板内查看 Input、Output、Events、Attributes、Links，可跳转关联日志并返回原订单调查。`order_node`、`order_tab`、`order_view` 保存在 URL，刷新恢复节点与 Tree / Waterfall 视角。Waterfall 按实际开始时间编号分组，每条 Trace 使用独立刻度，按节点相对开始和耗时定位类型色横条；支持逐组及逐节点折叠、缩放和重置。详情不提供全部展开/折叠按钮。时间跨度包含等待，不能作为累加耗时。

仅订单、Trace、Span、父 Span、事件、请求、Causation 和任务 ID 等关键标识提供 Lucide 复制图标；普通字段、指标、时间、状态和原始 JSON 不添加复制按钮。点击后显示勾选图标与“已复制”反馈，随后恢复；复制不会触发表格行跳转。剪贴板失败时展示可选择的原值与重试入口。`python tests/observability/workspace_copy_check.py` 验证实际剪贴板读回、成功反馈、失败手动复制与重试、逐 Trace 刻度和缩放重置。

生命周期接口保留原订单匹配 timeline，并增加每个 execution 的安全 Span 数据、`identifier_match`、`spans_truncated` 和 `span_limit`。最多 20 条 Trace，每条最多 200 个节点；超限、详情读取失败和后端不可用明确显示。独立 Trace 详情仍可进一步查看其已有采集范围。没有遥测证据的业务步骤不补造。

### 跨工作区关联调查

日志详情可进入关联订单、指定 Trace / Span、事件和来源事件；Trace 详情与列表可反向进入订单。事件查询分别使用 Event ID 与 Causation ID，展示已观测候选执行，不根据时间先后补造生产消费关系。服务详情可进入服务 Trace、日志和监控。

指标详情提供整个查询时段及单个数据点附近的 Trace / 日志入口，告警提供对应时段的服务和错误 Trace 查询。压测报告提供运行起止时间内的 Trace、日志和历史监控入口；只有时间条件时，明确标为候选证据，不宣称归属于该次压测。日志和指标接口支持受限的显式 `start` / `end`，最大跨度 30 天，数据是否存在仍由后端保留策略决定。

关联跳转保留原 URL、所选记录、节点、视角和局部滚动位置，返回入口可逐层回到原调查；日志记录和指标详情也支持刷新恢复。返回栈存储在当前浏览器会话内，最多八层。关键 ID 复制保持独立，不触发跳转。

`python tests/observability/investigation_navigation_check.py` 使用真实订单和 Span 数据、明确标识的日志夹具，验证日志 / 订单 / 指定 Span 连续往返、事件查询、压测时间范围与图表调查返回；不会创建订单、付款或运行压测。

详情面板点击外部关闭，通过原关闭入口同步清除 URL 选择并取消待完成请求；弹窗、下拉菜单与复制失败提示不触发误关闭。嵌套面板优先关闭最上层。列表主图标统一 16px、元信息图标 14px，图标与首行文字 / 元信息居中对齐，选中背景覆盖整行。`python tests/observability/detail_interaction_check.py` 验证图标来源、行对齐、完整选中态与外部关闭。

工作台动效由 `controls.css` / `controls.js` 统一管理：操作状态 120ms、菜单与内容切换 160ms、详情面板开合 220ms。面板和菜单支持淡入淡出与轻微位移；关闭时立即更新 URL 与逻辑状态并禁止命中，快速重新打开可反转退出过渡。旧浏览器降级为入场动画与即时关闭。节点详情、Tab 和指标分类仅在主动切换时过渡，后台轮询与搜索输入不触发内容动画，图表保持真实数据而不做数值插值。已有树分支和筛选栏折叠动画保持不变。

复制成功、工具提示和新建任务弹窗提供轻量反馈。遵循 `prefers-reduced-motion`，同时取消 CSS 与 JavaScript 动画；切换时不改变局部滚动，也不使用滚动惯性。`python tests/observability/workspace_motion_check.py` 验证真实菜单与详情开合、立即关闭状态、内容过渡、退出期间重开及减少动态效果模式，不写入业务数据。
