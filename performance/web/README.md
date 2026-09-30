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
