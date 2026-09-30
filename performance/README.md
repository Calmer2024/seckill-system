# Seckill Performance Platform v1

This directory provides the repository-local, one-command performance platform for the seckill system.

## Standalone web controller

The performance console is intentionally separate from the existing React storefront. Start it from the repository root:

```powershell
./performance/web/start-web.ps1
```

如果不希望占用当前 PowerShell 窗口，可以使用后台模式：

```powershell
./performance/web/start-web.ps1 -Background
```

Open `http://127.0.0.1:8099` to configure a run, monitor its state, inspect run history, and view the generated JSON report directly in the browser. The page also lets you select an existing report as the comparison baseline. It invokes the same `performance/run-test.ps1` entrypoint and keeps its mandatory `-ConfirmTarget` traffic guard.

## Start a run

Run PowerShell from the repository root. The confirmation switch is mandatory because these commands generate real traffic and may stop services during chaos tests.

```powershell
.\performance\run-test.ps1 -Scenario product-read -ConfirmTarget -WithMonitoring
.\performance\run-test.ps1 -Scenario seckill-contention -ConfirmTarget -WithMonitoring
.\performance\run-test.ps1 -Scenario traffic-spike -ConfirmTarget -WithMonitoring
.\performance\run-test.ps1 -Scenario stability-soak -ConfirmTarget -WithMonitoring
```

The default test data is isolated to product `900001` and user IDs `9000001` through `9010000`. Adjust these values when another authorized environment already uses that range.

Reports are written to `performance/reports/runs/<run-id>/`:

- `report.json` contains machine-readable load, business, consistency, and Prometheus data.
- `report.csv` contains a flat metric table suitable for spreadsheets.
- `report.html` contains a self-contained review page.
- `validation.json` contains the invariant checks and their actual values.

## Baseline comparison

The default `distributed` mode enables cache, read replica, Redis Lua reservation, Kafka async processing, and Outbox. The `baseline` mode disables those switches through `performance/config/docker-compose.baseline.yml`.

Run the same scenario in both modes and compare the second report with the first:

```powershell
.\performance\run-test.ps1 -Scenario product-read -Mode baseline -ConfirmTarget
.\performance\run-test.ps1 -Scenario product-read -Mode distributed -ConfirmTarget -CompareTo .\performance\reports\runs\<baseline-run>\report.json
```

The comparison is descriptive. It does not invent capacity numbers; all values come from the actual run.

## Monitoring

`-WithMonitoring` starts Prometheus on `http://localhost:9090` and Grafana on `http://localhost:3000` with `admin/admin`. The dashboard includes HTTP RPS and latency, errors, product cache hit rate, Redis, MySQL, Kafka lag, and container resource panels.

## Fault injection

The scripts under `performance/chaos/` stop and restore Compose services. They do not delete data. Use them during a separately named run, wait for the configured recovery window, and then inspect the generated consistency and lag results.

## Credibility boundary

The platform is intended for local bottleneck analysis, business correctness, and medium-scale concurrency validation. Docker Desktop shares CPU, memory, network, load generation, and monitoring resources on one host, so the results are not a production capacity claim.
