[CmdletBinding()]
param(
    [ValidateSet('product-read', 'seckill-contention', 'traffic-spike', 'stability-soak')]
    [string]$Scenario = 'product-read',
    [ValidateSet('distributed', 'baseline')]
    [string]$Mode = 'distributed',
    [string]$BaseUrl = 'http://frontend_nginx',
    [int]$ProductId = 900001,
    [int]$InitialStock = 100,
    [int]$UserIdStart = 9000001,
    [int]$UserCount = 10000,
    [int]$ConvergenceWaitSeconds = 15,
    [string]$RunId = (Get-Date -Format 'yyyyMMdd-HHmmss'),
    [string]$CompareTo,
    [switch]$WithMonitoring,
    [switch]$SkipReset,
    [switch]$NoBuild,
    [switch]$ConfirmTarget
)

$ErrorActionPreference = 'Stop'

if (-not $ConfirmTarget) {
    throw "Performance traffic is disabled by default. Re-run with -ConfirmTarget after verifying the target is authorized."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

$composeFiles = @('docker-compose.yml')
if ($Mode -eq 'baseline') {
    $composeFiles += 'performance/config/docker-compose.baseline.yml'
}

$composeArgs = @('compose')
foreach ($composeFile in $composeFiles) {
    $composeArgs += @('-f', $composeFile)
}

$env:PERF_PRODUCT_ID = "$ProductId"
$env:PERF_USER_ID_START = "$UserIdStart"
$env:PERF_USER_COUNT = "$UserCount"
$env:PERF_INITIAL_STOCK = "$InitialStock"
$env:PERF_REDIS_RESERVATION_ENABLED = if ($Mode -eq 'baseline') { 'false' } else { 'true' }

function Invoke-Compose {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose command failed with exit code $LASTEXITCODE."
    }
}

function Invoke-PythonScript {
    param([string[]]$Arguments)
    $output = & python @Arguments
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    return $exitCode
}

$runDirectory = Join-Path $repoRoot "performance/reports/runs/$RunId"
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

Write-Host "Starting core services for scenario '$Scenario' in '$Mode' mode..."
$upArguments = $composeArgs + @('up', '-d')
if (-not $NoBuild) {
    $upArguments += '--build'
}
Invoke-Compose $upArguments

if ($WithMonitoring) {
    Write-Host 'Starting Prometheus, Grafana, and exporters...'
    Invoke-Compose ($composeArgs + @('--profile', 'monitoring', 'up', '-d'))
}

$dataArguments = @(
    'performance/data/reset-environment.py',
    '--product-id', $ProductId,
    '--initial-stock', $InitialStock,
    '--user-id-start', $UserIdStart,
    '--user-count', $UserCount
)
foreach ($composeFile in $composeFiles) {
    $dataArguments += @('--compose-file', $composeFile)
}

if (-not $SkipReset) {
    Write-Host 'Resetting the isolated performance data range...'
    $resetExit = Invoke-PythonScript $dataArguments
    if ($resetExit -ne 0) { throw "Performance data reset failed with exit code $resetExit." }

    Write-Host 'Seeding the isolated performance product and users...'
    $productSeed = @('performance/data/seed-products.py', '--product-id', $ProductId, '--initial-stock', $InitialStock)
    $userSeed = @('performance/data/seed-users.py', '--user-id-start', $UserIdStart, '--user-count', $UserCount)
    foreach ($composeFile in $composeFiles) {
        $productSeed += @('--compose-file', $composeFile)
        $userSeed += @('--compose-file', $composeFile)
    }
    $seedProductExit = Invoke-PythonScript $productSeed
    if ($seedProductExit -ne 0) { throw "Product seed failed with exit code $seedProductExit." }
    $seedUserExit = Invoke-PythonScript $userSeed
    if ($seedUserExit -ne 0) { throw "User seed failed with exit code $seedUserExit." }
}

$containerSummaryPath = "/reports/$RunId/k6-summary.json"
$scenarioPath = "/scripts/scenarios/$Scenario.js"
$k6Arguments = $composeArgs + @(
    '--profile', 'loadgen', 'run', '--rm', '--no-deps',
    '-e', "BASE_URL=$BaseUrl",
    '-e', "PRODUCT_ID=$ProductId",
    '-e', "USER_ID_START=$UserIdStart",
    '-e', "USER_COUNT=$UserCount",
    '-e', "PERF_RUN_ID=$RunId",
    'k6', 'run', '--summary-trend-stats=avg,min,med,max,p(90),p(95),p(99)', "--summary-export=$containerSummaryPath", $scenarioPath
)

Write-Host "Running k6 scenario '$Scenario'..."
$runStartEpoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
& docker @k6Arguments
$k6Exit = $LASTEXITCODE
if ($k6Exit -ne 0) {
    Write-Warning "k6 exited with code $k6Exit. The report will include the failed load result."
}

if ($ConvergenceWaitSeconds -gt 0) {
    Write-Host "Waiting $ConvergenceWaitSeconds seconds for asynchronous state to converge..."
    Start-Sleep -Seconds $ConvergenceWaitSeconds
}

$validationPath = Join-Path $runDirectory 'validation.json'
$validatorArguments = @(
    'performance/validators/validate_consistency.py',
    '--product-id', $ProductId,
    '--initial-stock', $InitialStock,
    '--user-id-start', $UserIdStart,
    '--user-count', $UserCount,
    '--output', $validationPath
)
foreach ($composeFile in $composeFiles) {
    $validatorArguments += @('--compose-file', $composeFile)
}
Write-Host 'Validating inventory, orders, idempotency, and Outbox convergence...'
$validationExit = Invoke-PythonScript $validatorArguments
if ($validationExit -ne 0) {
    Write-Warning "Business validation failed with exit code $validationExit."
}

$metricsPath = Join-Path $runDirectory 'prometheus.json'
if ($WithMonitoring) {
    Write-Host 'Collecting Prometheus end-of-run metrics...'
    $metricsExit = Invoke-PythonScript @(
        'performance/reports/collect_prometheus.py',
        '--prometheus-url', 'http://localhost:9090',
        '--start-time', $runStartEpoch,
        '--mode', $Mode,
        '--scenario', $Scenario,
        '--output', $metricsPath
    )
    if ($metricsExit -ne 0) {
        Write-Warning "Prometheus collection failed with exit code $metricsExit."
    }
}

$k6SummaryPath = Join-Path $runDirectory 'k6-summary.json'
$reportArguments = @(
    'performance/reports/generate_report.py',
    '--k6-summary', $k6SummaryPath,
    '--validation', $validationPath,
    '--output-dir', $runDirectory,
    '--run-id', $RunId,
    '--scenario', $Scenario,
    '--mode', $Mode
)
if ($WithMonitoring) {
    $reportArguments += @('--metrics', $metricsPath)
}
if ($CompareTo) {
    $reportArguments += @('--compare-to', $CompareTo)
}

Write-Host 'Generating JSON, CSV, and HTML reports...'
$reportExit = Invoke-PythonScript $reportArguments
if ($reportExit -ne 0) { throw "Report generation failed with exit code $reportExit." }

Write-Host "Reports: $runDirectory"
if ($WithMonitoring) {
    Write-Host 'Grafana: http://localhost:3000 (admin/admin)'
    Write-Host 'Prometheus: http://localhost:9090'
}
if ($k6Exit -ne 0 -or $validationExit -ne 0) {
    exit 2
}
