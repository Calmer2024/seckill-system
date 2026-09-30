const API_PREFIX = '/api/performance';

const DEFAULT_FORM = {
  scenario: 'product-read',
  mode: 'distributed',
  product_id: 900001,
  initial_stock: 100,
  user_id_start: 9000001,
  user_count: 10000,
  convergence_wait_seconds: 15,
  base_url: 'http://frontend_nginx',
  with_monitoring: true,
  skip_reset: false,
  build: false,
};

const SCENARIO_FALLBACK = [
  { name: 'product-read', label: '商品查询阶梯压测', description: '商品查询吞吐与延迟验证。', focus: [] },
  { name: 'seckill-contention', label: '秒杀库存争抢', description: '有限库存下的并发抢购验证。', focus: [] },
  { name: 'traffic-spike', label: '瞬时洪峰', description: '短时间流量洪峰抗冲击验证。', focus: [] },
  { name: 'stability-soak', label: '长时间稳定性', description: '持续运行下的资源与延迟漂移验证。', focus: [] },
];

const OBSERVABILITY_LABELS = {
  http_rps: 'HTTP 实际 RPS',
  http_p50_seconds: 'HTTP p50 延迟',
  http_p95_seconds: 'HTTP p95 延迟',
  http_p99_seconds: 'HTTP p99 延迟',
  http_error_rate: 'HTTP 错误率',
  product_cache_hit_rate: '商品缓存命中率',
  redis_connected_clients: 'Redis 连接数',
  mysql_threads_connected: 'MySQL 连接数',
  mysql_slow_queries: 'MySQL 慢查询速率',
  mysql_row_lock_waits: 'MySQL 锁等待次数',
  mysql_row_lock_time_ms: 'MySQL 锁等待时间',
  mysql_replica_lag_seconds: 'MySQL 主从延迟',
  kafka_max_lag: 'Kafka 最大积压',
  order_outbox_pending: '订单 Outbox 当前积压',
  inventory_outbox_pending: '库存 Outbox 当前积压',
  order_outbox_peak: '订单 Outbox 峰值',
  inventory_outbox_peak: '库存 Outbox 峰值',
  inventory_available: '库存可用量',
  inventory_reserved: '库存预占量',
  inventory_sold: '库存已售量',
  valid_orders: '有效订单数',
  state_converged: '业务状态已收敛',
  duplicate_order_groups: '重复订单组数',
  kafka_peak_lag: 'Kafka 运行期间峰值积压',
  order_outbox_peak_during_run: '订单 Outbox 运行期间峰值',
  inventory_outbox_peak_during_run: '库存 Outbox 运行期间峰值',
  http_rps_peak: 'HTTP 运行期间峰值 RPS',
  container_cpu_peak_cores: '主机容器峰值 CPU',
  container_memory_peak_bytes: '主机容器峰值内存',
};

const METRIC_LABELS = {
  actual_rps: '实际发送 RPS',
  completed_requests: '完成请求数',
  p50_latency_ms: 'p50 响应时间',
  p95_latency_ms: 'p95 响应时间',
  p99_latency_ms: 'p99 响应时间',
  http_error_rate: 'HTTP 错误率',
  timeouts: '超时请求数',
  orders_accepted: '成功下单',
  duplicate_requests: '重复请求',
  out_of_stock_requests: '库存不足',
  rejected_requests: '拒绝请求',
  auth_failures: '认证失败',
  business_success_rate: '业务成功率',
};

const CHECK_LABELS = {
  stock_non_negative: '库存非负',
  stock_conservation: '库存守恒',
  successful_order_matches_sold_stock: '订单与已售库存一致',
  confirmed_reservation_matches_successful_order: '确认预占与订单一致',
  no_duplicate_active_orders: '无重复有效订单',
  purchase_record_matches_successful_order: '购买记录与订单一致',
  no_unconfirmed_reservations: '无未确认预占',
  order_outbox_drained: '订单消息已清空',
  inventory_outbox_drained: '库存消息已清空',
  redis_stock_non_negative: 'Redis 库存非负',
};

const state = {
  scenarios: [],
  runs: [],
  selectedRun: null,
  pollTimer: null,
  refreshBusy: false,
  formBusy: false,
};

const elements = {
  scenario: document.querySelector('#scenario'),
  scenarioDescription: document.querySelector('#scenario-description'),
  scenarioFocus: document.querySelector('#scenario-focus'),
  compareTo: document.querySelector('#compare-to'),
  form: document.querySelector('#run-form'),
  startRun: document.querySelector('#start-run'),
  resetForm: document.querySelector('#reset-form'),
  stopRun: document.querySelector('#stop-run'),
  refreshRuns: document.querySelector('#refresh-runs'),
  confirmTarget: document.querySelector('#confirm-target'),
  activeRun: document.querySelector('#active-run'),
  runsBody: document.querySelector('#runs-body'),
  historyEmpty: document.querySelector('#history-empty'),
  reportEmpty: document.querySelector('#report-empty'),
  reportContent: document.querySelector('#report-content'),
  reportLinks: document.querySelector('#report-links'),
  reportMeta: document.querySelector('#report-meta'),
  loadMetrics: document.querySelector('#load-metrics'),
  businessMetrics: document.querySelector('#business-metrics'),
  validationSummary: document.querySelector('#validation-summary'),
  checksBody: document.querySelector('#checks-body'),
  observabilityMetrics: document.querySelector('#observability-metrics'),
  comparisonSection: document.querySelector('#comparison-section'),
  comparisonBody: document.querySelector('#comparison-body'),
  rawJson: document.querySelector('#raw-json'),
  controllerStatus: document.querySelector('#controller-status'),
  toast: document.querySelector('#toast'),
  overviewStatus: document.querySelector('#overview-status'),
  overviewRecent: document.querySelector('#overview-recent'),
  overviewCount: document.querySelector('#overview-count'),
  rawReportToggle: document.querySelector('#raw-report-toggle'),
};

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function scenarioByName(name) {
  return state.scenarios.find((item) => item.name === name) || SCENARIO_FALLBACK.find((item) => item.name === name);
}

function scenarioLabel(name) {
  return scenarioByName(name)?.label || name || '未知场景';
}

function modeLabel(mode) {
  return mode === 'baseline' ? '基线方案' : mode === 'distributed' ? '分布式优化' : mode || '未知';
}

function statusLabel(status) {
  return {
    queued: '排队中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
    interrupted: '中断 / 未知',
  }[status] || status || '未知';
}

function isActive(status) {
  return status === 'queued' || status === 'running';
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '未采集';
  const number = Number(value);
  if (!Number.isFinite(number)) return escapeHtml(value);
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(number);
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '未采集';
  const number = Number(value);
  if (!Number.isFinite(number)) return '未采集';
  return `${formatNumber(number * 100, 2)}%`;
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return escapeHtml(value);
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatDuration(start, end) {
  if (!start || !end) return '—';
  const elapsed = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(elapsed) || elapsed < 0) return '—';
  const seconds = elapsed / 1000;
  return seconds < 60 ? `${formatNumber(seconds, 1)} 秒` : `${formatNumber(seconds / 60, 1)} 分钟`;
}

function formatGeneric(value) {
  if (value === null || value === undefined || value === '') return '未采集';
  if (typeof value === 'number') return formatNumber(value);
  if (typeof value === 'object') return escapeHtml(Object.entries(value).map(([key, item]) => `${key}: ${item ?? '空'}`).join(' · '));
  return escapeHtml(value);
}

function formatObservabilityValue(key, value) {
  if (value === null || value === undefined || value === '') return '未采集';
  const number = Number(value);
  if (!Number.isFinite(number)) return escapeHtml(value);
  if (key.includes('rate') && !key.includes('rps')) return formatPercent(number);
  if (key.includes('p50_seconds') || key.includes('p95_seconds') || key.includes('p99_seconds')) {
    return `${formatNumber(number * 1000, 2)} ms`;
  }
  if (key.includes('lag_seconds') || key.includes('replica_lag')) return `${formatNumber(number, 2)} 秒`;
  if (key.includes('bytes')) return `${formatNumber(number / 1024 / 1024, 2)} MB`;
  if (key.includes('rps')) return `${formatNumber(number, 2)} req/s`;
  if (key.includes('cpu_peak_cores')) return `${formatNumber(number, 2)} cores`;
  if (key.includes('slow_queries')) return `${formatNumber(number, 3)} /s`;
  return formatNumber(number);
}

function metricCard(label, value, suffix = '', tone = '') {
  const missing = value === null || value === undefined || value === '';
  const rendered = missing ? '未采集' : value;
  return `<div class="metric-card ${tone} ${missing ? 'is-missing' : ''}">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(rendered)}</strong>
    ${suffix ? `<small>${escapeHtml(suffix)}</small>` : ''}
  </div>`;
}

function detailItem(label, value, suffix = '') {
  const rendered = value === null || value === undefined || value === '' ? '未采集' : value;
  return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(rendered)}</strong>${suffix ? `<small>${escapeHtml(suffix)}</small>` : ''}</div>`;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_PREFIX}${path}`, {
    headers: { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
    ...options,
  });
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text || response.statusText };
  }
  if (!response.ok) throw new Error(payload.error || `请求失败（${response.status}）`);
  return payload;
}

function showToast(message, tone = 'info') {
  elements.toast.textContent = message;
  elements.toast.className = `toast is-visible ${tone}`;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.className = 'toast';
  }, 3600);
}

function closeSelects(except = null) {
  document.querySelectorAll('.custom-select').forEach((root) => {
    if (root === except) return;
    root.querySelector('.select-menu').hidden = true;
    root.querySelector('.select-trigger').setAttribute('aria-expanded', 'false');
  });
}

function setSelectOptions(name, options, preferred) {
  const root = document.querySelector(`[data-select="${name}"]`);
  const input = root.querySelector('input');
  const menu = root.querySelector('.select-menu');
  const selected = options.find((item) => item.value === (preferred ?? input.value)) || options[0];
  root._options = options;
  menu.innerHTML = options.map((item) => `<button class="select-option" type="button" role="option" aria-selected="${item.value === selected.value}" data-value="${escapeHtml(item.value)}">${escapeHtml(item.label)}</button>`).join('');
  input.value = selected.value;
  root.querySelector('.select-trigger span').textContent = selected.label;
}

document.querySelectorAll('.custom-select').forEach((root) => {
  const trigger = root.querySelector('.select-trigger');
  const menu = root.querySelector('.select-menu');
  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    const willOpen = menu.hidden;
    closeSelects(root);
    menu.hidden = !willOpen;
    trigger.setAttribute('aria-expanded', String(willOpen));
  });
  menu.addEventListener('click', (event) => {
    event.stopPropagation();
    const option = event.target.closest('[data-value]');
    if (!option) return;
    const input = root.querySelector('input');
    input.value = option.dataset.value;
    root.querySelector('.select-trigger span').textContent = root._options.find((item) => item.value === input.value)?.label || '';
    menu.querySelectorAll('[role="option"]').forEach((item) => item.setAttribute('aria-selected', String(item === option)));
    closeSelects();
    trigger.focus();
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  trigger.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const options = root._options || [];
      const index = options.findIndex((item) => item.value === root.querySelector('input').value);
      const next = options[(index + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length];
      if (next) menu.querySelector(`[data-value="${CSS.escape(next.value)}"]`)?.click();
    }
  });
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.custom-select')) closeSelects();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeSelects();
});

function renderScenarioOptions() {
  const scenarios = state.scenarios.length ? state.scenarios : SCENARIO_FALLBACK;
  setSelectOptions('scenario', scenarios.map((item) => ({ value: item.name, label: item.label })), DEFAULT_FORM.scenario);
  renderScenarioDetails();
}

function renderScenarioDetails() {
  const item = scenarioByName(elements.scenario.value) || SCENARIO_FALLBACK[0];
  elements.scenarioDescription.textContent = item.description || '';
  elements.scenarioFocus.innerHTML = (item.focus || []).map((focus) => `<span>${escapeHtml(focus)}</span>`).join('');
}

function renderRuns() {
  const runs = state.runs;
  elements.overviewCount.textContent = String(runs.length);
  elements.overviewRecent.textContent = runs[0] ? scenarioLabel(runs[0].request?.scenario || runs[0].report_metadata?.scenario) : '暂无记录';
  elements.historyEmpty.hidden = runs.length > 0;
  elements.runsBody.innerHTML = runs.map((run) => {
    const selected = state.selectedRun?.run_id === run.run_id ? 'is-selected' : '';
    const reportAction = run.report_available
      ? `<button class="table-link" type="button" data-select-run="${escapeHtml(run.run_id)}">查看</button>`
      : '<span class="muted">等待</span>';
    return `<tr class="${selected}">
      <td><button class="run-id-link" type="button" data-select-run="${escapeHtml(run.run_id)}">${escapeHtml(run.run_id)}</button></td>
      <td>${escapeHtml(scenarioLabel(run.request?.scenario || run.report_metadata?.scenario))}</td>
      <td>${escapeHtml(modeLabel(run.request?.mode || run.report_metadata?.mode))}</td>
      <td><span class="status-badge status-${escapeHtml(run.status)}">${escapeHtml(statusLabel(run.status))}</span></td>
      <td>${reportAction}</td>
    </tr>`;
  }).join('');
  renderComparisonOptions();
}

function renderComparisonOptions() {
  if (!elements.compareTo) return;
  const previous = elements.compareTo.value;
  const options = state.runs
    .filter((run) => run.report_available && run.run_id !== state.selectedRun?.run_id)
    .map((run) => ({ value: run.run_id, label: `${scenarioLabel(run.request?.scenario || run.report_metadata?.scenario)} · ${run.run_id}` }));
  setSelectOptions('compare-to', [{ value: '', label: '不生成对比' }, ...options], previous);
}

function renderActiveRun(task) {
  if (!task) {
    elements.activeRun.className = 'empty-state compact-empty';
    elements.activeRun.innerHTML = '<svg class="empty-icon"><use href="/icons.svg#pulse"></use></svg><strong>暂无运行任务</strong>';
    elements.overviewStatus.textContent = '待命';
    elements.stopRun.hidden = true;
    return;
  }
  const request = task.request || {};
  elements.overviewStatus.textContent = statusLabel(task.status);
  const logLines = task.log_lines?.length ? task.log_lines.join('\n') : '暂无控制器输出';
  elements.stopRun.hidden = !isActive(task.status);
  elements.activeRun.className = 'active-run-body';
  elements.activeRun.innerHTML = `<div class="active-status-row">
      <span class="status-badge status-${escapeHtml(task.status)}">${escapeHtml(statusLabel(task.status))}</span>
      <span class="phase-text">${escapeHtml(task.phase || '—')}</span>
    </div>
    <div class="active-run-id"><span>任务编号</span><strong>${escapeHtml(task.run_id)}</strong></div>
    <div class="active-meta-grid">
      <div><span>场景</span><strong>${escapeHtml(scenarioLabel(request.scenario))}</strong></div>
      <div><span>模式</span><strong>${escapeHtml(modeLabel(request.mode))}</strong></div>
      <div><span>开始时间</span><strong>${escapeHtml(formatDate(task.started_at || task.created_at))}</strong></div>
      <div><span>耗时</span><strong>${escapeHtml(formatDuration(task.started_at, task.ended_at))}</strong></div>
    </div>
    ${task.error ? `<div class="inline-error">${escapeHtml(task.error)}</div>` : ''}
    <div class="log-block"><div class="log-heading"><span>控制器日志</span><span>${escapeHtml(task.last_log || '')}</span></div><pre>${escapeHtml(logLines)}</pre></div>`;
}

function renderReportLinks(task) {
  if (!task?.files) {
    elements.reportLinks.innerHTML = '';
    return;
  }
  const links = [
    ['k6-summary.json', 'k6 原始结果'],
    ['report.json', 'JSON'],
    ['report.csv', 'CSV'],
    ['report.html', 'HTML'],
    ['validation.json', '校验 JSON'],
    ['controller.log', '日志'],
  ];
  elements.reportLinks.innerHTML = links
    .filter(([file]) => task.files[file])
    .map(([file, label]) => `<a href="${escapeHtml(task.files[file])}" ${file === 'report.html' ? 'target="_blank" rel="noreferrer"' : 'download'}>${escapeHtml(label)}</a>`)
    .join('');
}

function renderReport(task) {
  const report = task?.report;
  renderReportLinks(task);
  if (!report) {
    elements.reportEmpty.hidden = false;
    elements.reportContent.hidden = true;
    return;
  }
  elements.reportEmpty.hidden = true;
  elements.reportContent.hidden = false;

  const metadata = report.metadata || {};
  const validation = report.validation || {};
  const load = report.load || {};
  const business = report.business || {};
  const observability = report.observability || {};
  const validationState = validation.checks?.length ? (validation.passed ? '通过' : '失败') : '未采集';
  const validationClass = validationState === '通过' ? 'pass' : validationState === '失败' ? 'fail' : 'unknown';

  elements.reportMeta.innerHTML = `<div><span class="meta-label">任务编号</span><strong>${escapeHtml(metadata.run_id || task.run_id)}</strong></div>
    <div><span class="meta-label">场景</span><strong>${escapeHtml(scenarioLabel(metadata.scenario))}</strong></div>
    <div><span class="meta-label">模式</span><strong>${escapeHtml(modeLabel(metadata.mode))}</strong></div>
    <div><span class="meta-label">生成时间</span><strong>${escapeHtml(formatDate(metadata.generated_at))}</strong></div>
    <div><span class="meta-label">代码版本</span><strong class="revision-value">${escapeHtml(metadata.git_revision || '未记录')}</strong></div>
    <div><span class="meta-label">一致性</span><strong class="${validationClass}">${validationState}</strong></div>`;

  elements.loadMetrics.innerHTML = [
    metricCard(METRIC_LABELS.actual_rps, formatNumber(load.actual_rps), 'req/s', 'accent'),
    metricCard(METRIC_LABELS.completed_requests, formatNumber(load.completed_requests), 'requests'),
    metricCard(METRIC_LABELS.p50_latency_ms, formatNumber(load.p50_latency_ms), 'ms'),
    metricCard(METRIC_LABELS.p95_latency_ms, formatNumber(load.p95_latency_ms), 'ms', 'accent'),
    metricCard(METRIC_LABELS.p99_latency_ms, formatNumber(load.p99_latency_ms), 'ms', 'accent'),
    metricCard(METRIC_LABELS.http_error_rate, formatPercent(load.http_error_rate), '', load.http_error_rate > 0 ? 'danger' : ''),
    metricCard(METRIC_LABELS.timeouts, formatNumber(load.timeouts), 'requests', load.timeouts > 0 ? 'danger' : ''),
  ].join('');

  elements.businessMetrics.innerHTML = [
    detailItem(METRIC_LABELS.orders_accepted, formatNumber(business.orders_accepted), 'orders'),
    detailItem(METRIC_LABELS.duplicate_requests, formatNumber(business.duplicate_requests), 'requests'),
    detailItem(METRIC_LABELS.out_of_stock_requests, formatNumber(business.out_of_stock_requests), 'requests'),
    detailItem(METRIC_LABELS.rejected_requests, formatNumber(business.rejected_requests), 'requests'),
    detailItem(METRIC_LABELS.auth_failures, formatNumber(business.auth_failures), 'requests'),
    detailItem(METRIC_LABELS.business_success_rate, formatPercent(business.business_success_rate)),
  ].join('');

  const checks = validation.checks || [];
  elements.validationSummary.innerHTML = `<div class="validation-result ${validationClass}"><strong>${escapeHtml(validationState)}</strong><span>${checks.length ? `${checks.filter((item) => item.passed).length} / ${checks.length} 项通过` : '报告没有包含校验明细'}</span></div>`;
  elements.checksBody.innerHTML = checks.length ? checks.map((item) => `<tr>
    <td>${escapeHtml(CHECK_LABELS[item.name] || item.name || '未命名校验')}</td>
    <td><span class="check-state ${item.passed ? 'pass' : 'fail'}">${item.passed ? '通过' : '失败'}</span></td>
    <td>${formatGeneric(item.actual)}</td><td>${formatGeneric(item.expected)}</td><td>${formatGeneric(item.details)}</td>
  </tr>`).join('') : '<tr><td colspan="5" class="table-empty">未采集校验明细</td></tr>';

  const observabilityItems = [
    ...Object.entries(observability.metrics || {}).map(([key, value]) => ({ key, value, group: '运行结束' })),
    ...Object.entries(observability.peaks_during_run || {}).map(([key, value]) => ({ key, value, group: '运行期间峰值' })),
  ];
  const baselineInactive = new Set(['product_cache_hit_rate', 'kafka_max_lag', 'kafka_peak_lag']);
  const productReadInactive = new Set(['kafka_max_lag', 'kafka_peak_lag']);
  const statusLabels = { not_applicable: '不适用', collector_error: '采集异常', missing: '未采集' };
  elements.observabilityMetrics.innerHTML = observabilityItems.length
    ? observabilityItems.map(({ key, value, group }) => {
      const status = observability.metric_status?.[key] || ((metadata.mode === 'baseline' && baselineInactive.has(key)) || (metadata.scenario === 'product-read' && productReadInactive.has(key)) ? 'not_applicable' : value === null || value === undefined ? 'missing' : 'ok');
      const display = statusLabels[status] || formatObservabilityValue(key, value);
      return `<div class="observation-item ${status !== 'ok' ? 'is-missing' : ''}"><span>${escapeHtml(OBSERVABILITY_LABELS[key] || key)}</span><strong>${escapeHtml(display)}</strong><small>${escapeHtml(group)}</small></div>`;
    }).join('')
    : '<div class="observability-empty">本次运行未包含 Prometheus 指标。</div>';

  const comparison = report.comparison || {};
  const comparisonItems = Object.entries(comparison);
  elements.comparisonSection.hidden = comparisonItems.length === 0;
  elements.comparisonBody.innerHTML = comparisonItems.map(([key, item]) => `<tr>
    <td>${escapeHtml(METRIC_LABELS[key] || key)}</td><td>${formatGeneric(item.baseline)}</td><td>${formatGeneric(item.current)}</td>
    <td>${item.improvement_ratio === null || item.improvement_ratio === undefined ? '未计算' : formatPercent(item.improvement_ratio)}</td>
    <td>${item.direction === 'higher_is_better' ? '越高越好' : '越低越好'}</td>
  </tr>`).join('');
  elements.rawJson.textContent = JSON.stringify(report, null, 2);
}

function renderAll() {
  renderRuns();
  renderActiveRun(state.selectedRun);
  renderReport(state.selectedRun);
}

async function selectRun(runId) {
  try {
    const task = await api(`/runs/${encodeURIComponent(runId)}`);
    state.selectedRun = task;
    renderAll();
    startPollingIfNeeded();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function loadRuns() {
  const payload = await api('/runs');
  state.runs = payload.runs || [];
  renderRuns();
  if (!state.selectedRun && state.runs[0]) await selectRun(state.runs[0].run_id);
}

async function refreshSelected() {
  if (!state.selectedRun || state.refreshBusy) return;
  state.refreshBusy = true;
  try {
    const task = await api(`/runs/${encodeURIComponent(state.selectedRun.run_id)}`);
    state.selectedRun = task;
    renderAll();
    if (!isActive(task.status)) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
      await loadRuns();
    }
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    state.refreshBusy = false;
  }
}

function startPollingIfNeeded() {
  window.clearInterval(state.pollTimer);
  state.pollTimer = null;
  if (state.selectedRun && isActive(state.selectedRun.status)) {
    state.pollTimer = window.setInterval(refreshSelected, 1600);
  }
}

function formPayload() {
  const formData = new FormData(elements.form);
  return {
    scenario: formData.get('scenario'),
    mode: formData.get('mode'),
    product_id: Number(formData.get('product_id')),
    initial_stock: Number(formData.get('initial_stock')),
    user_id_start: Number(formData.get('user_id_start')),
    user_count: Number(formData.get('user_count')),
    convergence_wait_seconds: Number(formData.get('convergence_wait_seconds')),
    base_url: formData.get('base_url'),
    compare_to: elements.compareTo?.value || null,
    with_monitoring: document.querySelector('#with-monitoring').checked,
    skip_reset: document.querySelector('#skip-reset').checked,
    build: document.querySelector('#build-images').checked,
    confirm_target: elements.confirmTarget.checked,
  };
}

function setFormDefaults() {
  setSelectOptions('scenario', (state.scenarios.length ? state.scenarios : SCENARIO_FALLBACK).map((item) => ({ value: item.name, label: item.label })), DEFAULT_FORM.scenario);
  document.querySelector(`input[name="mode"][value="${DEFAULT_FORM.mode}"]`).checked = true;
  document.querySelector('#product-id').value = DEFAULT_FORM.product_id;
  document.querySelector('#initial-stock').value = DEFAULT_FORM.initial_stock;
  document.querySelector('#user-id-start').value = DEFAULT_FORM.user_id_start;
  document.querySelector('#user-count').value = DEFAULT_FORM.user_count;
  document.querySelector('#convergence-wait').value = DEFAULT_FORM.convergence_wait_seconds;
  setSelectOptions('base-url', [{ value: 'http://frontend_nginx', label: 'Docker 网关' }, { value: 'http://host.docker.internal', label: '宿主机' }], DEFAULT_FORM.base_url);
  renderComparisonOptions();
  setSelectOptions('compare-to', document.querySelector('[data-select="compare-to"]')._options, '');
  document.querySelector('#with-monitoring').checked = DEFAULT_FORM.with_monitoring;
  document.querySelector('#skip-reset').checked = DEFAULT_FORM.skip_reset;
  document.querySelector('#build-images').checked = DEFAULT_FORM.build;
  elements.confirmTarget.checked = false;
  elements.startRun.disabled = true;
  renderScenarioDetails();
}

async function submitRun(event) {
  event.preventDefault();
  if (!elements.confirmTarget.checked || state.formBusy) return;
  for (const [id, minimum] of [['product-id', 1], ['initial-stock', 1], ['user-id-start', 1], ['user-count', 1], ['convergence-wait', 0]]) {
    const field = document.getElementById(id);
    if (!/^\d+$/.test(field.value.trim()) || !Number.isSafeInteger(Number(field.value)) || Number(field.value) < minimum) {
      field.focus();
      showToast(`请填写有效的${field.closest('.field-group').querySelector('label').textContent}`, 'error');
      return;
    }
  }
  state.formBusy = true;
  elements.startRun.disabled = true;
  elements.startRun.textContent = '提交中…';
  try {
    const task = await api('/runs', { method: 'POST', body: JSON.stringify(formPayload()) });
    state.selectedRun = task;
    renderAll();
    startPollingIfNeeded();
    await loadRuns();
    showToast(`任务 ${task.run_id} 已启动`, 'success');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    state.formBusy = false;
    elements.startRun.disabled = !elements.confirmTarget.checked;
    elements.startRun.textContent = '启动压测';
  }
}

async function stopSelectedRun() {
  if (!state.selectedRun || !isActive(state.selectedRun.status)) return;
  elements.stopRun.disabled = true;
  try {
    const task = await api(`/runs/${encodeURIComponent(state.selectedRun.run_id)}/stop`, { method: 'POST' });
    state.selectedRun = task;
    renderAll();
    startPollingIfNeeded();
    await loadRuns();
    showToast('已发送停止请求', 'success');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    elements.stopRun.disabled = false;
  }
}

async function checkController() {
  try {
    const payload = await api('/health');
    elements.controllerStatus.className = 'connection-status is-online';
    elements.controllerStatus.innerHTML = `<i></i>控制器在线 · ${escapeHtml(payload.controller || 'local')}`;
  } catch {
    elements.controllerStatus.className = 'connection-status is-offline';
    elements.controllerStatus.innerHTML = '<i></i>控制器未连接';
  }
}

elements.scenario.addEventListener('change', renderScenarioDetails);
elements.rawReportToggle.addEventListener('click', () => {
  const expanded = elements.rawReportToggle.getAttribute('aria-expanded') === 'true';
  elements.rawReportToggle.setAttribute('aria-expanded', String(!expanded));
  elements.rawJson.hidden = expanded;
});
elements.confirmTarget.addEventListener('change', () => {
  elements.startRun.disabled = !elements.confirmTarget.checked || state.formBusy;
});
elements.form.addEventListener('submit', submitRun);
elements.resetForm.addEventListener('click', setFormDefaults);
elements.stopRun.addEventListener('click', stopSelectedRun);
elements.refreshRuns.addEventListener('click', async () => {
  try {
    await loadRuns();
    await refreshSelected();
    showToast('运行历史已刷新', 'success');
  } catch (error) {
    showToast(error.message, 'error');
  }
});
elements.runsBody.addEventListener('click', (event) => {
  const button = event.target.closest('[data-select-run]');
  if (button) selectRun(button.dataset.selectRun);
});

async function boot() {
  renderScenarioOptions();
  setFormDefaults();
  await checkController();
  try {
    await loadRuns();
  } catch (error) {
    showToast(`无法读取运行历史：${error.message}`, 'error');
  }
  renderAll();
}

boot();
