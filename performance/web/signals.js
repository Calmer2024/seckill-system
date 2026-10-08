window.workspaceSignals = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
  let active = null, timer = null, monitorBusy = false, logGeneration = 0;
  const date = seconds => new Date(seconds * 1000).toLocaleString('zh-CN', {hour12:false});
  async function read(kind, query = '') {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/api/observability/' + kind + query, {cache:'no-store', signal:controller.signal});
      if (!response.ok) throw new Error(response.status === 400 ? '查询条件无效。' : '查询服务不可用，请检查采集组件。');
      return await response.json();
    } finally { clearTimeout(timeout); }
  }
  function mount() {
    document.querySelector('#workspace-monitoring .workspace-heading').insertAdjacentHTML('afterend', `
      <section class="signal-panel"><div class="p0-heading"><div><h2>环境指标</h2><p>当前环境的请求、依赖和业务证据。</p></div><form id="metrics-window" class="trace-filters"><label>时间范围<select name="window"><option value="5">最近 5 分钟</option><option value="15" selected>最近 15 分钟</option><option value="60">最近 1 小时</option></select></label><button class="button button-quiet">刷新</button></form></div><p id="metrics-message" class="domain-note" aria-live="polite"></p><div id="environment-charts" class="signal-grid"></div></section>
      <section class="signal-panel"><div class="p0-heading"><div><h2>告警与通知</h2><p>当前活动告警与已持久化的触发、恢复通知。</p></div><button id="refresh-alerts" class="button button-quiet">刷新告警</button></div><p id="alerts-message" class="domain-note" aria-live="polite"></p><div id="active-alerts"></div><details><summary>通知记录</summary><div id="alert-notifications" class="table-wrap"></div></details></section>`);
    document.querySelector('#environment-charts').insertAdjacentHTML('afterend', '<p class="domain-note">HTTP 可用性目标暂设 99.9%，错误预算图按匹配路由的 5xx 比例计算。低流量与短历史不能证明 SLO 达标；无数据不视为零。生产验收尚未完成。<a href="/docs/observability/p4-runbooks.md" target="_blank" rel="noreferrer">SLO 与验收说明</a></p>');
    document.querySelector('#logs-content').innerHTML = `<section class="signal-panel"><form id="log-search" class="trace-filters">
      <label>服务<select name="service"><option value="">所有服务</option>${['user','product','order-api','inventory-api','order-worker','inventory-worker','gateway'].map(s=>`<option>${s}</option>`).join('')}</select></label>
      <label>时间范围<select name="window"><option value="5">最近 5 分钟</option><option value="15" selected>最近 15 分钟</option><option value="60">最近 1 小时</option></select></label>
      <label>级别<select name="level"><option value="">所有级别</option>${['DEBUG','INFO','WARNING','ERROR','CRITICAL'].map(s=>`<option>${s}</option>`).join('')}</select></label>
      <label>Trace ID<input name="trace_id" maxlength="32" pattern="[0-9a-fA-F]{32}"></label><label>订单 ID<input name="order_id" maxlength="19" pattern="[1-9][0-9]{0,18}"></label>
      <label>事件 ID<input name="event_id" maxlength="36"></label><label>Request ID<input name="request_id" maxlength="64"></label><label>正文包含<input name="text" maxlength="80"></label><input name="at" type="hidden">
      <button class="button button-quiet">查询日志</button><button id="clear-log-correlation" class="button button-quiet" type="button">回到当前时间</button></form>
      <p id="logs-message" class="domain-note" aria-live="polite">尚未查询。集中采集应用 JSON 与网关 JSON 访问日志。</p><div id="log-results"></div></section>`;
    document.querySelector('#log-search').addEventListener('submit', event => {event.preventDefault(); searchLogs();});
    document.querySelector('#log-search').elements.trace_id.addEventListener('input', () => {document.querySelector('#log-search').elements.at.value='';});
    document.querySelector('#clear-log-correlation').addEventListener('click', () => {document.querySelector('#log-search').elements.at.value=''; searchLogs();});
    document.querySelector('#metrics-window').addEventListener('submit', event => {event.preventDefault(); refreshMonitoring();});
    document.querySelector('#refresh-alerts').addEventListener('click', refreshAlerts);
    document.querySelector('#log-results').addEventListener('click', event => {
      const button = event.target.closest('[data-open-trace]');
      if (button) window.dispatchEvent(new CustomEvent('observability:open', {detail:{page:'traces',trace_id:button.dataset.openTrace}}));
    });
  }
  function chart(item) {
    const names = {missing:'此范围内无采集数据',unavailable:'指标查询失败',stale:'业务审计失败或过期'};
    const header = `<div class="signal-chart-heading"><div><h3>${esc(item.title)}</h3><small>${esc(item.unit)} · 时间序列</small></div><button data-expand-chart="${esc(item.id)}" aria-label="放大 ${esc(item.title)}"><svg aria-hidden="true"><use href="/icons.svg#arrows-out"></use></svg></button></div>`;
    if (item.status !== 'ok') return `<article class="signal-chart">${header}<p class="signal-empty">${esc(names[item.status] || '未采集')}</p></article>`;
    const all = item.series.flatMap(series=>series.points.filter(point=>point[1] !== null));
    if (!all.length) return `<article class="signal-chart">${header}<p class="signal-empty">此范围内无有效数值</p></article>`;
    const minTime = Math.min(...all.map(p=>p[0])), maxTime = Math.max(...all.map(p=>p[0]));
    const minimum = Math.min(0,...all.map(p=>p[1])), maximum = Math.max(...all.map(p=>p[1])) || 1;
    const colors=['#006ddd','#047647','#ac5305','#b42318','#7c3aed','#0891b2'];
    const x = t=>40+(t-minTime)/Math.max(1,maxTime-minTime)*480, y=v=>125-(v-minimum)/Math.max(.0001,maximum-minimum)*105;
    const paths = item.series.map((series,index)=>{let gap=true; const path=series.points.map(([t,v])=>{if(v===null){gap=true;return '';}const command=gap?'M':'L';gap=false;return `${command}${x(t).toFixed(1)},${y(v).toFixed(1)}`;}).join(' ');return `<path d="${path}" fill="none" stroke="${colors[index%colors.length]}" stroke-width="1.5"/>`;}).join('');
    const legends=item.series.map((series,index)=>{const latest=series.points.at(-1)?.[1];const label=Object.values(series.labels).join(' · ') || '环境';return `<span style="color:${colors[index%colors.length]}">${esc(label)} ${latest===null || latest===undefined?'无数据':Number(latest).toLocaleString('zh-CN',{maximumFractionDigits:3})}</span>`;}).join('');
    return `<article class="signal-chart">${header}<svg viewBox="0 0 550 155" role="img" aria-label="${esc(item.title)} 时间序列">${[20,55,90,125].map(y=>`<line x1="40" y1="${y}" x2="520" y2="${y}" stroke="#e2e8f0" stroke-dasharray="4 4"/>`).join('')}<text x="0" y="24">${maximum.toLocaleString('zh-CN',{maximumSignificantDigits:3})}</text><text x="0" y="128">${minimum.toFixed(0)}</text>${paths}<text x="40" y="150">${esc(new Date(minTime*1000).toLocaleTimeString('zh-CN'))}</text><text x="450" y="150">${esc(new Date(maxTime*1000).toLocaleTimeString('zh-CN'))}</text></svg><div class="signal-legend">${legends}</div></article>`;
  }
  async function refreshMonitoring() {
    if(monitorBusy) return;
    monitorBusy=true;
    const requestedWindow=document.querySelector("#metrics-window").elements.window.value;
    try {
      const query=new URLSearchParams(new FormData(document.querySelector('#metrics-window'))),url=new URLSearchParams(location.search);
      if(url.has('monitor_start')){query.set('start',url.get('monitor_start'));query.set('end',url.get('monitor_end'));}
      const payload=await read('metrics','?'+query);
      document.querySelector('#metrics-message').textContent=`本地环境 · ${query.has('start')?date(payload.start)+' — '+date(payload.end):'最近 '+payload.window_minutes+' 分钟'} · 查询时间 ${date(payload.sampled_at)} · ${query.has('start')?'历史指标证据':payload.business_evidence_fresh?'业务审计证据新鲜':'业务审计证据缺失或过期，请检查采集器'}`;
      document.querySelector('#environment-charts').innerHTML=payload.charts.map(chart).join('');window.unifiedWorkspace?.metrics(payload);
    } catch(error) {document.querySelector('#metrics-message').textContent=error.message;document.querySelector('#environment-charts').textContent='查询失败，未显示零值。';window.unifiedWorkspace?.metricsFailed();}
    finally {monitorBusy=false;if(active==='monitoring'&&document.querySelector("#metrics-window").elements.window.value!==requestedWindow)queueMicrotask(refreshMonitoring);}
  }
  let alertGeneration=0;
  async function refreshAlerts() {
    const generation=++alertGeneration;
    try {
      const payload=await read('alerts');
      if(generation!==alertGeneration)return;
      document.querySelector('#alerts-message').textContent=`查询时间 ${date(payload.sampled_at)} · 告警查询${payload.alert_status==='ok'?'正常':'不可用'} · 通知存储${payload.notification_status==='ok'?'正常':'不可用'} · 通知接收渠道：本地工作台`;
      document.querySelector('#active-alerts').innerHTML=payload.alert_status!=='ok'?'<p>告警查询失败，不能认定无告警。</p>':payload.alerts.length?payload.alerts.map(item=>`<article class="signal-alert"><span class="p0-status p0-down">${esc(item.labels.severity || 'warning')}</span><span>${esc(item.labels.alertname)}</span><p>${esc(item.annotations.summary || '')}</p><small>${esc(item.labels.service || item.labels.job || '')} · ${esc(item.labels.instance || '')} · ${esc(item.starts_at)}</small> <a href="/docs/observability/p3-runbooks.md" target="_blank" rel="noreferrer">排障手册</a></article>`).join(''):'<p class="domain-note">当前无未抑制的活动告警。</p>';
      window.unifiedWorkspace?.alerts(payload);
      document.querySelector('#alert-notifications').innerHTML=payload.notification_status!=='ok'?'<p>无法读取通知存储。</p>':`<table><thead><tr><th>接收时间</th><th>状态</th><th>告警</th><th>摘要</th></tr></thead><tbody>${payload.notifications.length?payload.notifications.map(item=>`<tr><td>${esc(date(item.received_at))}</td><td>${item.status==='resolved'?'已恢复':'已触发'}</td><td>${esc(item.labels.alertname)}</td><td>${esc(item.annotations.summary)}</td></tr>`).join(''):'<tr><td colspan="4">暂无通知记录。</td></tr>'}</tbody></table>`;
    }catch(error){if(generation===alertGeneration){document.querySelector('#alerts-message').textContent=error.message;window.unifiedWorkspace?.alerts({alerts:[],alert_status:'unavailable'});}}
  }
  async function searchLogs() {
    const generation=++logGeneration;
    const form=document.querySelector('#log-search'), query=new URLSearchParams(new FormData(form));
    if(!query.get('at'))query.delete('at');
    for(const key of ['start','end'])if(!query.get(key))query.delete(key);
    document.querySelector('#logs-message').textContent='正在查询集中日志…';
    try {
      const payload=await read('logs','?'+query);
      if(generation!==logGeneration)return;
      document.querySelector('#logs-message').textContent=`本地环境 · ${form.elements.start?.value?'指定时段 '+date(Number(form.elements.start.value))+' — '+date(Number(form.elements.end.value)):form.elements.at.value?'链路发生时段':'最近 '+payload.window_minutes+' 分钟'} · ${payload.logs.length} 条 · 最多 ${payload.limit} 条${payload.truncated?'，请缩小范围':''} · 查询时间 ${date(payload.sampled_at)}。未采样请求可能只有日志，没有 Trace。`;
      if(window.unifiedWorkspace){window.unifiedWorkspace.logs(payload.logs);}else document.querySelector('#log-results').innerHTML=payload.logs.length?payload.logs.map(item=>{const f=item.fields;return `<article class="log-entry"><div class="log-meta"><time>${esc(new Date(Number(item.timestamp_ns)/1e6).toLocaleString('zh-CN',{hour12:false}))}</time><span>${esc(f.level || '未知')}</span><span>${esc(item.service)} / ${esc(item.instance)}</span>${f.trace_id?`<button class="trace-link" type="button" data-open-trace="${esc(f.trace_id)}">${esc(f.trace_id)}</button>`:''}</div><p>${esc(f.message || f.event || f.route_template || '')}</p><details><summary>结构化字段</summary><pre>${esc(JSON.stringify(f,null,2))}</pre></details></article>`;}).join(''):'<p class="signal-empty">此范围内无日志。请检查时间、筛选条件与采集状态。</p>';
    }catch(error){if(generation!==logGeneration)return;document.querySelector('#logs-message').textContent=error.message;document.querySelector('#log-results').textContent='日志查询失败，未展示为空结果。';}
  }
  function activate(page) {
    if(page===active)return;
    active=page;clearInterval(timer);timer=null;
    if(page==='monitoring'){refreshMonitoring();refreshAlerts();timer=setInterval(()=>{refreshMonitoring();refreshAlerts();},15000);}
    if(page==='logs')searchLogs();
  }
  function openLogs(traceId,at) {
    const form=document.querySelector('#log-search');form.reset();form.elements.trace_id.value=traceId;form.elements.at.value=at || '';window.unifiedWorkspace?.syncLogQuery();searchLogs();
  }
  return {mount,activate,openLogs,renderChart:chart};
})();
