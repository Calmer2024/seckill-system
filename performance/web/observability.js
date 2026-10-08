// P0 status lives inside the existing performance workspace. It is environment data, not run data.
window.performanceObservability = (() => {
  let timer = null;
  let busy = false;
  let lastSample = null;
  const labels = {
    up: '正常', down: '不可用', degraded: '后台任务异常', stale: '采集已过期',
    stalled: '轮询停滞', not_configured: '未配置采集', not_instrumented: '未接入任务指标',
    unavailable: '采集不可用', partial: '部分采集异常',
  };
  const taskLabels = {
    'order-outbox-publisher': '订单消息发布',
    'inventory-result-consumer': '库存结果消费',
    'payment-result-consumer': '支付结果消费',
    'inventory-outbox-publisher': '库存结果发布',
    'inventory-order-created-consumer': '订单消息消费',
  };
  const html = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;',
  }[char]));
  const age = (value) => value === null || value === undefined ? '无记录' :
    value < 60 ? `${Math.floor(value)} 秒前` : value < 3600 ? `${Math.floor(value / 60)} 分钟前` : `${Math.floor(value / 3600)} 小时前`;
  const badge = (status) => `<span class="p0-status p0-${html(status)}">${html(labels[status] || status)}</span>`;

  function render(payload) {
    document.querySelector('#p0-source').textContent =
      `环境：本地 · 来源：${payload.source} · 采集时间：${new Date(payload.sampled_at).toLocaleString('zh-CN')} · ${payload.status === 'ok' ? '查询成功' : '采集异常，请检查 Prometheus 和目标状态'}`;
    document.querySelector('#p0-capabilities').innerHTML =
      `<span>Metrics：${payload.status === 'unavailable' ? '采集不可用' : '已查询实际目标'}</span><span>集中日志：在「日志」页查询</span><span>应用 JSON 日志：已配置</span>`;
    document.querySelector('#p0-service-status').innerHTML = payload.services.flatMap((service) => {
      const tasks = service.tasks?.length ? service.tasks : [null];
      return tasks.map((task, index) => `<tr>
        ${index === 0 ? `<td rowspan="${tasks.length}">${html(service.service)}<small class="p0-instance" title="${html(service.instance || '无采集目标')}">${html(service.instance || '无采集目标')}</small></td><td rowspan="${tasks.length}">${badge(service.status)}</td>` : ''}
        <td title="${html(task?.role || '')}">${task ? html(taskLabels[task.role] || task.role) + '<small>' + html(labels[task.status] || task.status) + '</small>' : '不适用'}</td>
        <td>${task ? `轮询 ${html(age(task.poll_age_seconds))}<small>业务进度 ${html(age(task.progress_age_seconds))}</small>` : '不适用'}</td>
        <td>${task ? html(task.failures ?? '未采集') : '不适用'}</td></tr>`);
    }).join('');
  }

  async function refresh() {
    if (busy || document.hidden) return;
    busy = true;
    const button = document.querySelector('#refresh-observability');
    button.disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    try {
      const response = await fetch('/api/observability/status', { signal: controller.signal, cache: 'no-store' });
      if (!response.ok) throw new Error('controller unavailable');
      const payload = await response.json();
      render(payload);
      lastSample = payload.sampled_at;
    } catch {
      document.querySelector('#p0-source').textContent = lastSample
        ? `刷新失败。下表为最后已知状态，采集时间 ${new Date(lastSample).toLocaleString('zh-CN')}，不能代表当前健康状态。`
        : '环境状态采集失败，请检查压测控制器。';
      if (!lastSample) document.querySelector('#p0-service-status').innerHTML = '<tr><td colspan="5" class="table-empty">采集失败，未显示零值或健康状态。</td></tr>';
    } finally {
      clearTimeout(timeout);
      button.disabled = false;
      busy = false;
    }
  }

  let activePage = null;
  function activate(page) {
    if (page === activePage) return;
    activePage = page;
    if (page !== 'traces') window.traceExplorer.deactivate();
    window.workspaceSignals?.activate(page);
    if (timer) clearInterval(timer);
    timer = null;
    if (page === 'monitoring') {
      refresh();
      timer = setInterval(refresh, 10000);
    } else if (page === 'traces') {
      window.traceExplorer.activate();
    }
  }
  function mount() {
    window.workspaceSignals.mount();
    document.querySelector('#refresh-observability').addEventListener('click', refresh);
    window.traceExplorer.mount();
  }
  return { activate, mount, openTrace: (...args) => window.traceExplorer.open(...args) };
})();
